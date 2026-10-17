"""Excel 导入 / 导出 · 模板生成、逐行校验、原子导入。

规则：
- 模板由系统提供，业务方不可自改列名；
- 逐行校验，错误行返回「行号 + 字段 + 错误说明」，前端高亮；
- 存在错误行时**不写入任何数据**（原子性），绝不部分写入脏数据。
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import MARKET_PROJECT_ID_PREFIX, MARKET_STAGE_VALUES, MARKET_STAGES, SCOPES, TASK_ID_PREFIX
from app.models import (
    TaskGroup,
    MarketProject,
    MetricActual,
    MetricDef,
    Organization,
    ProjectProgress,
    Role,
    Task,
    TaskProgress,
    User,
)

# 系统默认任务组：导入时「任务分类」留空则归到它
TG_NONE_ID = "TG_NONE"

# ------------------------------------------------------------------ 模板列定义
#
# 列名与「任务管理」列表、编辑表单保持同一套叫法，避免同一字段多处异名：
#   列表、表单与模板列名保持同一套叫法：一律称「任务名称 / 任务分类 / 任务描述」。

TASK_COLUMNS = [
    "任务名称",
    "任务分类",
    "任务描述",
    "是否异常",
    "目标",
    "已完成",
    "数量单位",
    "任务进展",
    "计划开始日期",
    "计划结束日期",
    "责任部门",
    "责任人",
]

# 可选列：老版本模板（无「数量单位」等）仍可导入，缺失时按空值处理
TASK_OPTIONAL_COLUMNS = {"任务分类", "任务描述", "数量单位", "是否异常"}

# 导出列 = 任务ID + 全部可填写列 + 系统列 —— 导出文件可直接当导入模板回灌
TASK_SYSTEM_EXPORT_COLUMNS = ["完成进度", "状态", "创建人", "创建时间", "更新时间"]
TASK_EXPORT_COLUMNS = ["任务ID"] + TASK_COLUMNS + TASK_SYSTEM_EXPORT_COLUMNS

METRIC_COLUMNS = ["指标编码", "指标名称", "统计周期", "统计组织", "实际值"]

# ---------------------------------------------------------------- 蓝色清新配色
_BLUE_DARK = "1F4E79"    # 深蓝：标题文字
_BLUE_MAIN = "2E75B6"    # 主蓝：表头背景
_BLUE_LIGHT = "DEEBF7"   # 浅蓝：说明栏背景
_BLUE_SOFT = "F7FBFF"    # 极浅蓝：示例行背景
_BLUE_BORDER = "BDD7EE"  # 淡蓝：边框 / 斑马纹
_GRAY_NOTE = "5B6B7C"    # 说明文字

_HEADER_FILL = PatternFill("solid", fgColor=_BLUE_MAIN)
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_BANNER_FILL = PatternFill("solid", fgColor=_BLUE_LIGHT)
_SAMPLE_FILL = PatternFill("solid", fgColor=_BLUE_SOFT)
_THIN = Side(style="thin", color=_BLUE_BORDER)
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
_BODY_ALIGN = Alignment(horizontal="left", vertical="center", wrap_text=False)

# 说明栏占 3 行：标题 / 操作提示 / 留白；表头固定在第 4 行
BANNER_ROWS = 3
HEADER_ROW = BANNER_ROWS + 1


class RowError(dict):
    pass


def _write_banner(ws, n_cols: int, title: str, lines: list[str]) -> None:
    """写顶部说明栏：整行合并，浅蓝底 + 深蓝标题，下面跟操作提示。"""
    last = get_column_letter(n_cols)

    ws.merge_cells(f"A1:{last}1")
    c = ws["A1"]
    c.value = title
    c.font = Font(bold=True, size=13, color=_BLUE_DARK)
    c.alignment = Alignment(horizontal="left", vertical="center")
    c.fill = _BANNER_FILL
    ws.row_dimensions[1].height = 28

    ws.merge_cells(f"A2:{last}2")
    c2 = ws["A2"]
    c2.value = "　".join(lines)
    c2.font = Font(size=9, color=_GRAY_NOTE)
    c2.alignment = Alignment(horizontal="left", vertical="center")
    c2.fill = _BANNER_FILL
    ws.row_dimensions[2].height = 20

    ws.row_dimensions[3].height = 6
    for col in range(1, n_cols + 1):
        for row in (1, 2, 3):
            ws.cell(row=row, column=col).fill = _BANNER_FILL


def _style_header(ws, row_idx: int, columns: list[str]) -> None:
    """表头：主蓝底白字、居中、冻结、列宽自适应（中文字符按 2 倍宽估算）。"""
    for idx, name in enumerate(columns, start=1):
        cell = ws.cell(row=row_idx, column=idx, value=name)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _HEADER_ALIGN
        cell.border = _BORDER
        width = sum(2 if ord(ch) > 127 else 1 for ch in name) + 6
        ws.column_dimensions[get_column_letter(idx)].width = max(12, min(30, width))
    ws.row_dimensions[row_idx].height = 24
    # 用字符串定位冻结窗格：若用 ws.cell(...) 会创建一个空单元格，
    # 使后续 ws.append 从下一行开始，模板里就会多出一行空白。
    ws.freeze_panes = f"A{row_idx + 1}"


def _style_data_rows(ws, first_row: int, last_row: int, n_cols: int, sample_rows: int = 1) -> None:
    """数据区加淡蓝细边框；示例行用极浅蓝弱化。"""
    for row in range(first_row, last_row + 1):
        for col in range(1, n_cols + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = _BORDER
            cell.alignment = _BODY_ALIGN
            if row - first_row < sample_rows:
                cell.fill = _SAMPLE_FILL


def _notes_sheet(wb: Workbook, title: str, rows: list[list[str]], widths=(22, 74)):
    """「填写说明」页：统一的蓝色表头 + 细边框。"""
    ws = wb.create_sheet(title)
    for i, row in enumerate(rows):
        ws.append(row)
        r = ws.max_row
        for col in range(1, len(row) + 1):
            cell = ws.cell(row=r, column=col)
            cell.border = _BORDER
            if i == 0:
                cell.fill = _HEADER_FILL
                cell.font = _HEADER_FONT
                cell.alignment = _HEADER_ALIGN
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                cell.font = Font(size=10)
                if col == 1:
                    cell.font = Font(size=10, bold=True, color=_BLUE_DARK)
    ws.row_dimensions[1].height = 22
    ws.column_dimensions["A"].width = widths[0]
    ws.column_dimensions["B"].width = widths[1]
    ws.freeze_panes = "A2"
    return ws


def _safe_sheet_name(wb: Workbook, name: str) -> str:
    used = {ws.title for ws in wb.worksheets}
    if name not in used:
        return name
    i = 1
    while f"{name}{i}" in used:
        i += 1
    return f"{name}{i}"


# ------------------------------------------------------------------ 模板生成


TASK_TEMPLATE_NOTES = [
    ["填写项", "说明"],
    ["任务名称", "必填。公司级重点任务标题；同名多行会自动归组为同一任务"],
    ["任务分类", "选填。部门/班组级承接任务，可为空"],
    ["任务描述", "选填。任务的背景与交付要求"],
    ["是否异常", "选填，只能填「是」或「否」，默认否"],
    ["目标", "必填。数字，非量化任务填 1"],
    ["已完成", "必填。数字，非量化任务未完成填 0、完成填 1"],
    ["数量单位", "选填。如 万元 / 台 / 项，留空则不显示单位"],
    ["任务进展", "必填。当前进展说明，导入后作为该任务的第一条进展记录"],
    ["计划开始日期", "必填，格式 2026-10-01"],
    ["计划结束日期", "必填，格式 2026-12-31，不能早于开始日期"],
    ["责任部门", "必填。组织名称或编码（见「组织清单」页）"],
    ["责任人", "必填。必须是系统内已有账号姓名"],
    ["任务ID / 完成进度 / 状态 / 创建人 / 创建时间 / 更新时间", "由系统自动生成，不在模板中填写"],
]


def build_task_template(db: Session) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "任务数据"

    _write_banner(
        ws,
        len(TASK_COLUMNS),
        "重点任务导入标准模板",
        ["请勿修改第 4 行字段名称", "从第 5 行开始逐行填写", "灰色示例行可直接覆盖或删除"],
    )
    _style_header(ws, HEADER_ROW, TASK_COLUMNS)
    ws.append(
        [
            "完成全年营收目标 10.2 亿",
            "华东大区营收达成",
            "华东大区年度营收承接",
            "否",
            46000,
            31800,
            "万元",
            "Q3 累计 3.18 亿",
            "2026-01-01",
            "2026-12-31",
            "市场部",
            "郑凯",
        ]
    )
    _style_data_rows(ws, HEADER_ROW + 1, ws.max_row, len(TASK_COLUMNS), sample_rows=1)

    # 说明
    _notes_sheet(wb, "填写说明", TASK_TEMPLATE_NOTES)

    # 组织清单
    orgs = _notes_sheet(wb, "组织清单", [["编码", "名称"]])
    for o in db.scalars(select(Organization).order_by(Organization.sort_order, Organization.id)).all():
        orgs.append([o.id, o.name])
    for r in range(2, orgs.max_row + 1):
        for c in range(1, 3):
            orgs.cell(row=r, column=c).border = _BORDER

    # 数据验证：是否异常
    dv_abn = DataValidation(type="list", formula1='"是,否"', allow_blank=True)
    dv_abn.error = "只能填「是」或「否」"
    ws.add_data_validation(dv_abn)
    col_abn = get_column_letter(TASK_COLUMNS.index("是否异常") + 1)
    dv_abn.add(f"{col_abn}{HEADER_ROW + 1}:{col_abn}{HEADER_ROW + 2000}")

    # 数据验证：责任部门（引用组织清单）
    dv_dept = DataValidation(type="list", formula1="=组织清单!$B$2:$B$200", allow_blank=True)
    dv_dept.error = "责任部门需存在于组织清单"
    ws.add_data_validation(dv_dept)
    col_dept = get_column_letter(TASK_COLUMNS.index("责任部门") + 1)
    dv_dept.add(f"{col_dept}{HEADER_ROW + 1}:{col_dept}{HEADER_ROW + 2000}")

    # 数据验证：责任人（引用账号清单）
    dv_owner = DataValidation(type="list", formula1="=账号清单!$A$2:$A$300", allow_blank=True)
    dv_owner.error = "责任人需是系统内已有账号姓名"
    ws.add_data_validation(dv_owner)
    col_owner = get_column_letter(TASK_COLUMNS.index("责任人") + 1)
    dv_owner.add(f"{col_owner}{HEADER_ROW + 1}:{col_owner}{HEADER_ROW + 2000}")

    # 账号清单（供责任人下拉）
    users = _notes_sheet(wb, "账号清单", [["姓名", "部门"]])
    for u in db.scalars(select(User).order_by(User.id)).all():
        users.append([u.name, org_name_of(db, u.dept_id)])
    for r in range(2, users.max_row + 1):
        for c in range(1, 3):
            users.cell(row=r, column=c).border = _BORDER

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def org_name_of(db: Session, org_id: str | None) -> str:
    if not org_id:
        return ""
    o = db.get(Organization, org_id)
    return o.name if o else org_id


METRIC_TEMPLATE_NOTES = [
    ["填写项", "说明"],
    ["指标编码", "必填。见「指标清单」页"],
    ["指标名称", "选填，仅供人工核对，导入以编码为准"],
    ["统计周期", "必填。格式 2026-10，可选范围 2026-09 ~ 2099-12"],
    ["统计组织", "必填。组织编码，如 CO / PC1"],
    ["实际值", "必填。录入的是「截止当月」的累计值，纯数字、不带单位"],
]


def build_metric_template(db: Session) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "指标数据"

    _write_banner(
        ws,
        len(METRIC_COLUMNS),
        "指标数据导入标准模板",
        ["请勿修改第 4 行字段名称", "从第 5 行开始逐行填写", "灰色示例行可直接覆盖或删除"],
    )
    _style_header(ws, HEADER_ROW, METRIC_COLUMNS)
    ws.append(["REV_SALE", "销售收入", "2026-10", "CO", 9860])
    _style_data_rows(ws, HEADER_ROW + 1, ws.max_row, len(METRIC_COLUMNS), sample_rows=1)

    _notes_sheet(wb, "填写说明", METRIC_TEMPLATE_NOTES)

    metrics = _notes_sheet(
        wb, "指标清单", [["指标编码", "指标名称", "单位", "所属组", "统计组织"]], widths=(18, 24)
    )
    for m in db.scalars(select(MetricDef).order_by(MetricDef.sort_order, MetricDef.id)).all():
        scope_hint = "CO / PC1-PCn" if m.group in ("annual", "project") else "CO"
        metrics.append([m.id, m.name, m.unit, m.group, scope_hint])
    for r in range(2, metrics.max_row + 1):
        for c in range(1, 6):
            metrics.cell(row=r, column=c).border = _BORDER

    dv_metric = DataValidation(type="list", formula1="=指标清单!$A$2:$A$200", allow_blank=True)
    dv_metric.error = "指标编码需存在于指标清单"
    ws.add_data_validation(dv_metric)
    dv_metric.add(f"A{HEADER_ROW + 1}:A{HEADER_ROW + 2000}")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ 解析


def _cell_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _locate_header_row(ws, columns: list[str], scan: int = 8) -> int:
    """找出表头所在行：取「命中列名最多」的那一行。

    模板顶部有说明栏，表头因此不固定在第 1 行；该策略同时兼容无说明栏的老模板。
    """
    best_row, best_hits = 1, -1
    limit = max(1, min(scan, ws.max_row or 1))
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=limit, values_only=True), start=1):
        vals = {_cell_str(v) for v in row}
        hits = sum(1 for c in columns if c in vals)
        if hits > best_hits:
            best_row, best_hits = i, hits
    return best_row


def parse_rows(
    file_bytes: bytes,
    columns: list[str],
    max_rows: int,
    optional: set[str] | None = None,
) -> list[dict]:
    """按列名定位取数（顺序无关）。

    - 表头行自动定位，允许模板顶部带说明栏；
    - `optional` 中的列缺失时不报错，按空值处理，便于老模板继续可用。
    """
    optional = optional or set()
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.worksheets[0]
    header_row = _locate_header_row(ws, columns)
    header = [_cell_str(c.value) for c in ws[header_row]]
    index = {name: header.index(name) for name in columns if name in header}
    missing = [c for c in columns if c not in index and c not in optional]
    if missing:
        raise ValueError(f"模板缺少列：{'、'.join(missing)}")

    rows: list[dict] = []
    for r in ws.iter_rows(min_row=header_row + 1, values_only=True):
        if all(_cell_str(v) == "" for v in r):
            continue
        rows.append({name: _cell_str(r[i]) if i < len(r) else "" for name, i in index.items()})
        if len(rows) > max_rows:
            raise ValueError(f"单次导入不能超过 {max_rows} 行")
    return rows


# ------------------------------------------------------------------ 校验


def _is_valid_date(s: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_task_rows(db: Session, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    valid: list[dict] = []
    org_ids = set(db.scalars(select(Organization.id)).all())
    org_names = set(db.scalars(select(Organization.name)).all())
    user_names = set(db.scalars(select(User.name)).all())

    for i, r in enumerate(rows):
        row_no = i + 2
        row_errors: list[dict] = []

        if not r.get("任务名称"):
            row_errors.append({"field": "任务名称", "msg": "不能为空"})

        if not (r.get("任务描述") or "").strip():
            row_errors.append({"field": "任务描述", "msg": "不能为空"})

        if not (r.get("任务进展") or "").strip():
            row_errors.append({"field": "任务进展", "msg": "不能为空"})

        abn = r.get("是否异常", "")
        if abn and abn not in ("是", "否"):
            row_errors.append({"field": "是否异常", "msg": "只能填「是」或「否」"})

        target_raw = r.get("目标", "")
        if target_raw == "":
            row_errors.append({"field": "目标", "msg": "不能为空"})
        else:
            try:
                if float(target_raw) <= 0:
                    row_errors.append({"field": "目标", "msg": "必须为正数，非量化任务填 1"})
            except ValueError:
                row_errors.append({"field": "目标", "msg": "必须为正数，非量化任务填 1"})

        done_raw = r.get("已完成", "")
        if done_raw == "":
            row_errors.append({"field": "已完成", "msg": "不能为空"})
        else:
            try:
                if float(done_raw) < 0:
                    row_errors.append({"field": "已完成", "msg": "必须为不小于 0 的数字"})
            except ValueError:
                row_errors.append({"field": "已完成", "msg": "必须为不小于 0 的数字"})

        start_raw, end_raw = r.get("计划开始日期", ""), r.get("计划结束日期", "")
        if not start_raw:
            row_errors.append({"field": "计划开始日期", "msg": "不能为空"})
        elif not _is_valid_date(start_raw):
            row_errors.append({"field": "计划开始日期", "msg": "日期格式应为 2026-10-01"})

        if not end_raw:
            row_errors.append({"field": "计划结束日期", "msg": "不能为空"})
        elif not _is_valid_date(end_raw):
            row_errors.append({"field": "计划结束日期", "msg": "日期格式应为 2026-12-31"})
        elif _is_valid_date(start_raw) and datetime.strptime(end_raw, "%Y-%m-%d") < datetime.strptime(start_raw, "%Y-%m-%d"):
            row_errors.append({"field": "计划结束日期", "msg": "不能早于计划开始日期"})

        dept = r.get("责任部门", "")
        if not dept:
            row_errors.append({"field": "责任部门", "msg": "不能为空"})
        elif dept not in org_ids and dept not in org_names:
            row_errors.append({"field": "责任部门", "msg": f"「{dept}」不是有效的组织名称或编码"})

        owner = r.get("责任人", "")
        if not owner:
            row_errors.append({"field": "责任人", "msg": "不能为空"})
        elif owner not in user_names:
            row_errors.append({"field": "责任人", "msg": f"「{owner}」不是系统内已有账号姓名"})

        if row_errors:
            for e in row_errors:
                errors.append({"row": row_no, **e})
        else:
            valid.append({**r, "_row": row_no})
    return valid, errors


def validate_metric_rows(db: Session, rows: list[dict], period: str) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    valid: list[dict] = []
    metric_ids = set(db.scalars(select(MetricDef.id)).all())
    org_ids = set(db.scalars(select(Organization.id)).all())

    for i, r in enumerate(rows):
        row_no = i + 2
        row_errors: list[dict] = []

        code = r.get("指标编码", "")
        if not code:
            row_errors.append({"field": "指标编码", "msg": "不能为空"})
        elif code not in metric_ids:
            row_errors.append({"field": "指标编码", "msg": f"指标编码「{code}」不存在"})

        p = r.get("统计周期", "")
        if not p:
            row_errors.append({"field": "统计周期", "msg": "不能为空"})
        elif p != period:
            row_errors.append({"field": "统计周期", "msg": f"与当前看板周期「{period}」不一致"})

        org = r.get("统计组织", "")
        if not org:
            row_errors.append({"field": "统计组织", "msg": "不能为空"})
        elif org not in org_ids:
            row_errors.append({"field": "统计组织", "msg": f"组织编码「{org}」不存在"})

        val = r.get("实际值", "")
        if val == "":
            row_errors.append({"field": "实际值", "msg": "不能为空"})
        else:
            try:
                float(val)
            except ValueError:
                row_errors.append({"field": "实际值", "msg": "必须是数字"})

        if row_errors:
            for e in row_errors:
                errors.append({"row": row_no, **e})
        else:
            valid.append({**r, "_row": row_no})
    return valid, errors


# ------------------------------------------------------------------ 入库


def next_task_id(db: Session) -> str:
    prefix = f"{TASK_ID_PREFIX}{date.today().year}"
    rows = db.scalars(select(Task.id).where(Task.id.like(f"{prefix}%"))).all()
    max_seq = 0
    for tid in rows:
        m = re.fullmatch(rf"{prefix}(\d+)", tid)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"{prefix}{max_seq + 1:04d}"


def next_task_group_id(db: Session) -> str:
    """生成下一个任务组 ID：TG + 4 位自增序号（系统默认 TG_NONE 不参与序号）。"""
    rows = db.scalars(select(TaskGroup.id)).all()
    max_seq = 0
    for mid in rows:
        m = re.fullmatch(r"TG(\d+)", mid or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"TG{max_seq + 1:04d}"


def _resolve_task_group(db: Session, name: str, user: User) -> TaskGroup:
    """按名称解析任务组：命中则返回，否则以导入者身份新建（「任务分类」即任务组名）。"""
    name = (name or "").strip()
    if not name:
        mt = db.get(TaskGroup, TG_NONE_ID)
        return mt  # 系统默认「空」必定存在（seed 已建）
    existing = db.scalar(select(TaskGroup).where(TaskGroup.name == name))
    if existing:
        return existing
    mt = TaskGroup(id=next_task_group_id(db), name=name, created_by=user.id)
    db.add(mt)
    db.flush()
    return mt


def import_tasks(db: Session, rows: list[dict], user: User) -> int:
    for r in rows:
        dept_raw = r["责任部门"]
        org = db.scalar(select(Organization).where(Organization.id == dept_raw))
        if not org:
            org = db.scalar(select(Organization).where(Organization.name == dept_raw))
        mt = _resolve_task_group(db, r.get("任务分类", ""), user)
        task = Task(
            id=next_task_id(db),
            parent=r["任务名称"],
            title=mt.name if mt else None,
            task_group_id=mt.id if mt else TG_NONE_ID,
            description=r.get("任务描述", ""),
            abnormal=r.get("是否异常") == "是",
            target=Decimal(str(r["目标"])),
            done=Decimal(str(r["已完成"])),
            unit=r.get("数量单位", ""),
            note=r.get("任务进展", ""),
            start_date=datetime.strptime(r["计划开始日期"], "%Y-%m-%d").date(),
            end_date=datetime.strptime(r["计划结束日期"], "%Y-%m-%d").date(),
            dept_id=org.id,
            owner=r["责任人"],
            created_by=user.id,
        )
        db.add(task)
        db.flush()
        # 任务进展为导入必填项：同时写入第一条进展记录（与手工新建同一套规则）
        if (r.get("任务进展") or "").strip():
            db.add(TaskProgress(task_id=task.id, content=r["任务进展"].strip(), created_by=user.id))
    return len(rows)


def import_metrics(db: Session, rows: list[dict], user: User) -> int:
    for r in rows:
        metric_id = r["指标编码"]
        org_id = r["统计组织"]
        period = r["统计周期"]
        value = Decimal(str(r["实际值"]))
        existing = db.scalar(
            select(MetricActual).where(
                MetricActual.metric_id == metric_id,
                MetricActual.org_id == org_id,
                MetricActual.period == period,
            )
        )
        if existing:
            existing.value = value
            existing.created_by = user.id
        else:
            db.add(MetricActual(metric_id=metric_id, org_id=org_id, period=period, value=value, created_by=user.id))
    return len(rows)


def _fmt_dt(iso: str) -> str:
    """ISO 时间 → 「YYYY-MM-DD HH:MM」（按本地时区渲染）。"""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def export_tasks(db: Session, rows: list[Task]) -> bytes:
    """导出任务清单。

    列与「任务管理」列表保持一致（业务列同名，另加任务ID与系统列），
    因此导出文件本身即可作为导入模板回灌。
    """
    from app.services.achievement import task_to_dict

    wb = Workbook()
    ws = wb.active
    ws.title = "任务列表"
    _write_banner(
        ws,
        len(TASK_EXPORT_COLUMNS),
        "重点任务清单",
        [f"共 {len(rows)} 项任务", "带「系统」字样的列由系统生成，回灌导入时会被忽略"],
    )
    _style_header(ws, HEADER_ROW, TASK_EXPORT_COLUMNS)

    user_names = {u.id: u.name for u in db.scalars(select(User)).all()}
    # 任务组名解析（按 ID → 名称），「空」输出为空串以便回灌时重新归到默认
    mt_ids = {t.task_group_id for t in rows if t.task_group_id}
    mt_names = (
        {mid: name for mid, name in db.execute(select(TaskGroup.id, TaskGroup.name).where(TaskGroup.id.in_(mt_ids))).all()}
        if mt_ids
        else {}
    )
    for t in rows:
        d = task_to_dict(t)
        main_name = mt_names.get(t.task_group_id, "") if t.task_group_id else ""
        ws.append(
            [
                d["id"],
                d["parent"],
                main_name,
                d["description"],
                "是" if d["abnormal"] else "否",
                d["target"],
                d["done"],
                d["unit"],
                d["note"],
                d["startDate"],
                d["endDate"],
                org_name_of(db, d["deptId"]),
                d["owner"],
                f"{d['progress']}%",
                d["statusLabel"],
                user_names.get(d.get("createdById", ""), ""),
                _fmt_dt(d.get("createdAt", "")),
                _fmt_dt(d.get("updatedAt", "")),
            ]
        )
    if ws.max_row >= HEADER_ROW + 1:
        _style_data_rows(ws, HEADER_ROW + 1, ws.max_row, len(TASK_EXPORT_COLUMNS), sample_rows=0)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ 账号导入
#
# 必填字段约定（与「账号管理」表单同一套叫法）：
#   姓名 / 账号 / 初始密码 / 所属部门 / 角色 / 数据可见范围
# 选填：状态（留空按「启用」）


ACCOUNT_COLUMNS = ["姓名", "账号", "初始密码", "所属部门", "角色", "数据可见范围", "状态"]
ACCOUNT_OPTIONAL_COLUMNS = {"状态"}

# 中文标签 → scope key（允许两种写法，与 constants.SCOPES 同源）
SCOPE_LABEL_TO_KEY: dict[str, str] = {label: key for key, label in SCOPES.items()}

# 状态中文 → 取值（留空默认启用）
STATUS_LABEL_TO_KEY: dict[str, str] = {"启用": "active", "停用": "disabled"}

ACCOUNT_TEMPLATE_NOTES = [
    ["填写项", "说明"],
    ["姓名", "必填。系统内显示名，也是任务 / 项目「责任人 / 负责人」下拉的可选项"],
    ["账号", "必填。登录账号，至少 2 个字符；库内与本次文件内均不可重复"],
    ["初始密码", "必填。至少 6 个字符"],
    ["所属部门", "必填。部门名称或编码，需存在于「部门清单」页"],
    ["角色", "必填。角色名称或编码，需存在于「角色清单」页"],
    ["数据可见范围", "必填。四选一：本人 / 本部门 / 本部门及下属部门 / 全公司"],
    ["状态", "选填。启用 / 停用，留空按「启用」处理"],
]


def build_account_template(db: Session) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "账号数据"

    _write_banner(
        ws,
        len(ACCOUNT_COLUMNS),
        "账号批量导入标准模板",
        ["请勿修改第 4 行字段名称", "从第 5 行开始逐行填写", "灰色示例行可直接覆盖或删除"],
    )
    _style_header(ws, HEADER_ROW, ACCOUNT_COLUMNS)
    ws.append(["郑凯", "zhengkai", "123456", "市场部", "普通成员", "本部门及下属部门", "启用"])
    _style_data_rows(ws, HEADER_ROW + 1, ws.max_row, len(ACCOUNT_COLUMNS), sample_rows=1)

    _notes_sheet(wb, "填写说明", ACCOUNT_TEMPLATE_NOTES)

    # 部门清单（供「所属部门」下拉）
    orgs = _notes_sheet(wb, "部门清单", [["编码", "名称"]])
    for o in db.scalars(select(Organization).order_by(Organization.sort_order, Organization.id)).all():
        orgs.append([o.id, o.name])
    for r in range(2, orgs.max_row + 1):
        for c in range(1, 3):
            orgs.cell(row=r, column=c).border = _BORDER

    # 角色清单（供「角色」下拉，附各角色默认可见范围）
    roles = _notes_sheet(wb, "角色清单", [["编码", "名称", "默认可见范围"]], widths=(18, 24))
    for ro in db.scalars(select(Role).order_by(Role.id)).all():
        roles.append([ro.id, ro.name, SCOPES.get(ro.scope, ro.scope)])
    for r in range(2, roles.max_row + 1):
        for c in range(1, 4):
            roles.cell(row=r, column=c).border = _BORDER

    dv_dept = DataValidation(type="list", formula1="=部门清单!$B$2:$B$200", allow_blank=True)
    dv_dept.error = "所属部门需存在于部门清单"
    ws.add_data_validation(dv_dept)
    col_dept = get_column_letter(ACCOUNT_COLUMNS.index("所属部门") + 1)
    dv_dept.add(f"{col_dept}{HEADER_ROW + 1}:{col_dept}{HEADER_ROW + 2000}")

    dv_role = DataValidation(type="list", formula1="=角色清单!$B$2:$B$200", allow_blank=True)
    dv_role.error = "角色需存在于角色清单"
    ws.add_data_validation(dv_role)
    col_role = get_column_letter(ACCOUNT_COLUMNS.index("角色") + 1)
    dv_role.add(f"{col_role}{HEADER_ROW + 1}:{col_role}{HEADER_ROW + 2000}")

    dv_scope = DataValidation(
        type="list", formula1='"' + ",".join(SCOPES.values()) + '"', allow_blank=True
    )
    dv_scope.error = "数据可见范围只能填：本人 / 本部门 / 本部门及下属部门 / 全公司"
    ws.add_data_validation(dv_scope)
    col_scope = get_column_letter(ACCOUNT_COLUMNS.index("数据可见范围") + 1)
    dv_scope.add(f"{col_scope}{HEADER_ROW + 1}:{col_scope}{HEADER_ROW + 2000}")

    dv_status = DataValidation(type="list", formula1='"启用,停用"', allow_blank=True)
    dv_status.error = "状态只能填「启用」或「停用」"
    ws.add_data_validation(dv_status)
    col_status = get_column_letter(ACCOUNT_COLUMNS.index("状态") + 1)
    dv_status.add(f"{col_status}{HEADER_ROW + 1}:{col_status}{HEADER_ROW + 2000}")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def validate_account_rows(db: Session, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """逐行校验账号导入数据。

    返回 (valid, errors)。errors 元素为 {row, errors:[{field,msg}]}，
    与任务导入的回执结构保持一致，前端可直接复用同一套展示。
    """
    errors: list[dict] = []
    valid: list[dict] = []

    org_by_name = {o.name: o.id for o in db.scalars(select(Organization)).all()}
    org_by_id = {o.id: o.id for o in db.scalars(select(Organization)).all()}
    role_by_name = {r.name: r.id for r in db.scalars(select(Role)).all()}
    role_by_id = {r.id: r.id for r in db.scalars(select(Role)).all()}
    taken_accounts = set(db.scalars(select(User.account)).all())

    for i, r in enumerate(rows):
        row_no = i + 2
        row_errors: list[dict] = []

        name = (r.get("姓名") or "").strip()
        account = (r.get("账号") or "").strip()
        password = (r.get("密码") or r.get("初始密码") or "").strip()
        dept = (r.get("所属部门") or "").strip()
        role = (r.get("角色") or "").strip()
        scope_raw = (r.get("数据可见范围") or "").strip()
        status_raw = (r.get("状态") or "").strip()

        if not name:
            row_errors.append({"field": "姓名", "msg": "不能为空"})
        elif len(name) > 32:
            row_errors.append({"field": "姓名", "msg": "不能超过 32 个字符"})

        if not account:
            row_errors.append({"field": "账号", "msg": "不能为空"})
        elif len(account) < 2:
            row_errors.append({"field": "账号", "msg": "至少 2 个字符"})
        elif len(account) > 32:
            row_errors.append({"field": "账号", "msg": "不能超过 32 个字符"})
        elif account in taken_accounts:
            row_errors.append({"field": "账号", "msg": "账号已存在"})
        else:
            taken_accounts.add(account)

        if not password:
            row_errors.append({"field": "初始密码", "msg": "不能为空"})
        elif len(password) < 6:
            row_errors.append({"field": "初始密码", "msg": "至少 6 个字符"})
        elif len(password) > 128:
            row_errors.append({"field": "初始密码", "msg": "不能超过 128 个字符"})

        dept_id = org_by_name.get(dept) or org_by_id.get(dept)
        if not dept:
            row_errors.append({"field": "所属部门", "msg": "不能为空"})
        elif not dept_id:
            row_errors.append({"field": "所属部门", "msg": "部门不存在，请参照「部门清单」页填写"})

        role_id = role_by_name.get(role) or role_by_id.get(role)
        if not role:
            row_errors.append({"field": "角色", "msg": "不能为空"})
        elif not role_id:
            row_errors.append({"field": "角色", "msg": "角色不存在，请参照「角色清单」页填写"})

        scope = SCOPE_LABEL_TO_KEY.get(scope_raw) or (scope_raw if scope_raw in SCOPES else None)
        if not scope_raw:
            row_errors.append({"field": "数据可见范围", "msg": "不能为空"})
        elif not scope:
            row_errors.append({"field": "数据可见范围", "msg": "只能填：本人 / 本部门 / 本部门及下属部门 / 全公司"})

        status = STATUS_LABEL_TO_KEY.get(status_raw, "active")
        if status_raw and not STATUS_LABEL_TO_KEY.get(status_raw):
            row_errors.append({"field": "状态", "msg": "只能填「启用」或「停用」"})

        if row_errors:
            # 与任务导入回执保持一致：每条错误一行，带行号 / 字段 / 原因
            for e in row_errors:
                errors.append({"row": row_no, **e})
        else:
            valid.append(
                {
                    "name": name,
                    "account": account,
                    "password": password,
                    "deptId": dept_id,
                    "roleId": role_id,
                    "scope": scope,
                    "status": status,
                }
            )
    return valid, errors


# ------------------------------------------------------------------ 市场项目导入 / 导出
#
# 列名与「项目管理」列表、编辑表单保持同一套叫法：项目名称 / 项目进展 / 项目描述 / 牵引车需求 /
# 挂车需求 / 项目阶段 / 负责人 / 所属部门。其中「项目描述」列表不展示，但导入模板、导出、新增/编辑/详情仍展示，
# 因此模板与导出都保留该列；「项目进展」为新增字段，导入后写入项目快照并生成第一条进展记录。

_STAGE_LABEL_TO_VALUE = {s["label"]: s["stage"] for s in MARKET_STAGES}
_STAGE_VALUE_TO_LABEL = {s["stage"]: s["label"] for s in MARKET_STAGES}

MARKET_PROJECT_COLUMNS = [
    "项目名称",
    "项目进展",
    "项目描述",
    "项目阶段",
    "负责人",
    "所属部门",
]

# 可选列：老版本模板（无「项目描述 / 所属部门」）仍可导入，缺失时按空值处理
MARKET_PROJECT_OPTIONAL_COLUMNS = {"项目描述", "所属部门"}

# 导出列 = 项目ID + 全部可填写列（不含车辆需求明细，导入模板也不含） + 汇总值 + 系统列。
# 与导入模板刻意不同：导入只填项目信息，车辆需求（车头/挂车）在系统里补充；
# 导出额外给出「车头数量 / 挂车数量」汇总值（= 明细数量合计），与列表 / 驾驶舱口径一致。
MARKET_PROJECT_SYSTEM_EXPORT_COLUMNS = ["项目ID", "创建人", "创建时间", "更新时间"]
MARKET_PROJECT_EXPORT_COLUMNS = [
    "项目ID",
    "项目名称",
    "项目进展",
    "项目描述",
    "项目阶段",
    "负责人",
    "所属部门",
    "车头数量",
    "挂车数量",
    "创建人",
    "创建时间",
    "更新时间",
]


def _resolve_stage(raw: Any) -> int | None:
    """把「项目阶段」解析为阶段值（10/25/50/75/90/100）。

    允许填数字（25）或阶段名称（市场尽调），其余返回 None（由校验层报「不合法」）。
    """
    raw = (raw or "").strip()
    if raw == "":
        return None
    if re.fullmatch(r"\d+", raw):
        v = int(raw)
    else:
        v = _STAGE_LABEL_TO_VALUE.get(raw)
    return v if v in MARKET_STAGE_VALUES else None


def next_market_project_id(db: Session) -> str:
    rows = db.scalars(select(MarketProject.id).where(MarketProject.id.like(f"{MARKET_PROJECT_ID_PREFIX}%"))).all()
    max_seq = 0
    for pid in rows:
        m = re.fullmatch(rf"{MARKET_PROJECT_ID_PREFIX}(\d+)", pid or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"{MARKET_PROJECT_ID_PREFIX}{max_seq + 1:04d}"


MARKET_PROJECT_TEMPLATE_NOTES = [
    ["填写项", "说明"],
    ["项目名称", "必填。市场项目名称"],
    ["项目进展", "必填。当前项目进展说明，导入后作为该项目的第一条进展记录"],
    ["项目描述", "选填。项目的背景与交付要求"],
    ["项目阶段", "必填。填 10/25/50/75/90/100 或阶段名称（项目导入/市场尽调/初审通过/联合评审通过/签约落地/交车投运）"],
    ["负责人", "必填。必须是系统内已有账号姓名"],
    ["所属部门", "选填。负责人直接所属部门，留空则按负责人自动带出"],
    ["车头需求 / 挂车需求", "不在导入模板内。导入后请在系统「编辑项目」中补充车辆型号、电池度数与数量"],
    ["项目ID / 创建人 / 创建时间 / 更新时间", "由系统自动生成，不在模板中填写"],
]


def build_market_project_template(db: Session) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "项目数据"

    _write_banner(
        ws,
        len(MARKET_PROJECT_COLUMNS),
        "市场项目导入标准模板",
        ["请勿修改第 4 行字段名称", "从第 5 行开始逐行填写", "灰色示例行可直接覆盖或删除", "车辆需求请在系统编辑中补充"],
    )
    _style_header(ws, HEADER_ROW, MARKET_PROJECT_COLUMNS)
    ws.append(
        [
            "华东物流园运力替换项目",
            "已完成需求调研，进入方案设计",
            "物流园 200 辆燃油重卡替换为新能源",
            25,
            "郑凯",
            "市场部",
        ]
    )
    _style_data_rows(ws, HEADER_ROW + 1, ws.max_row, len(MARKET_PROJECT_COLUMNS), sample_rows=1)

    # 说明
    _notes_sheet(wb, "填写说明", MARKET_PROJECT_TEMPLATE_NOTES)

    # 组织清单（供「所属部门」下拉）
    orgs = _notes_sheet(wb, "组织清单", [["编码", "名称"]])
    for o in db.scalars(select(Organization).order_by(Organization.sort_order, Organization.id)).all():
        orgs.append([o.id, o.name])
    for r in range(2, orgs.max_row + 1):
        for c in range(1, 3):
            orgs.cell(row=r, column=c).border = _BORDER

    dv_dept = DataValidation(type="list", formula1="=组织清单!$B$2:$B$200", allow_blank=True)
    dv_dept.error = "所属部门需存在于组织清单"
    ws.add_data_validation(dv_dept)
    col_dept = get_column_letter(MARKET_PROJECT_COLUMNS.index("所属部门") + 1)
    dv_dept.add(f"{col_dept}{HEADER_ROW + 1}:{col_dept}{HEADER_ROW + 2000}")

    # 数据验证：负责人（引用账号清单）
    dv_owner = DataValidation(type="list", formula1="=账号清单!$A$2:$A$300", allow_blank=True)
    dv_owner.error = "负责人需是系统内已有账号姓名"
    ws.add_data_validation(dv_owner)
    col_owner = get_column_letter(MARKET_PROJECT_COLUMNS.index("负责人") + 1)
    dv_owner.add(f"{col_owner}{HEADER_ROW + 1}:{col_owner}{HEADER_ROW + 2000}")

    # 数据验证：项目阶段（数字或名称皆可）
    dv_stage = DataValidation(
        type="list",
        formula1='"' + ",".join(str(v) for v in MARKET_STAGE_VALUES) + '"',
        allow_blank=True,
    )
    dv_stage.error = "项目阶段只能填 10/25/50/75/90/100 或阶段名称"
    ws.add_data_validation(dv_stage)
    col_stage = get_column_letter(MARKET_PROJECT_COLUMNS.index("项目阶段") + 1)
    dv_stage.add(f"{col_stage}{HEADER_ROW + 1}:{col_stage}{HEADER_ROW + 2000}")

    # 账号清单（供负责人下拉）
    users = _notes_sheet(wb, "账号清单", [["姓名", "部门"]])
    for u in db.scalars(select(User).order_by(User.id)).all():
        users.append([u.name, org_name_of(db, u.dept_id)])
    for r in range(2, users.max_row + 1):
        for c in range(1, 3):
            users.cell(row=r, column=c).border = _BORDER

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def validate_market_project_rows(db: Session, rows: list[dict]) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    valid: list[dict] = []
    org_ids = set(db.scalars(select(Organization.id)).all())
    org_names = set(db.scalars(select(Organization.name)).all())
    user_names = set(db.scalars(select(User.name)).all())

    for i, r in enumerate(rows):
        row_no = i + 2
        row_errors: list[dict] = []

        if not (r.get("项目名称") or "").strip():
            row_errors.append({"field": "项目名称", "msg": "不能为空"})

        if not (r.get("项目进展") or "").strip():
            row_errors.append({"field": "项目进展", "msg": "不能为空"})

        stage = _resolve_stage(r.get("项目阶段", ""))
        if stage is None:
            row_errors.append({"field": "项目阶段", "msg": "不合法，应为 10/25/50/75/90/100 或阶段名称"})

        owner = (r.get("负责人") or "").strip()
        if not owner:
            row_errors.append({"field": "负责人", "msg": "不能为空"})
        elif owner not in user_names:
            row_errors.append({"field": "负责人", "msg": f"「{owner}」不是系统内已有账号姓名"})

        dept = (r.get("所属部门") or "").strip()
        if dept and dept not in org_ids and dept not in org_names:
            row_errors.append({"field": "所属部门", "msg": f"「{dept}」不是有效的组织名称或编码"})

        if row_errors:
            for e in row_errors:
                errors.append({"row": row_no, **e})
        else:
            valid.append(
                {
                    **r,
                    "_row": row_no,
                    "_stage": stage,  # 校验已解析，导入直接复用
                    "_owner": owner,
                }
            )
    return valid, errors


def import_market_projects(db: Session, rows: list[dict], user: User) -> int:
    for r in rows:
        owner = r["_owner"]
        u = db.scalar(select(User).where(User.name == owner))
        dept_raw = (r.get("所属部门") or "").strip()
        dept_id = None
        if dept_raw:
            org = db.scalar(select(Organization).where(Organization.id == dept_raw))
            if not org:
                org = db.scalar(select(Organization).where(Organization.name == dept_raw))
            dept_id = org.id if org else None
        # 所属部门留空 → 按负责人自动带出（与编辑表单一致）
        if not dept_id and u:
            dept_id = u.dept_id
        pid = next_market_project_id(db)
        progress = (r["项目进展"] or "").strip()
        p = MarketProject(
            id=pid,
            name=(r["项目名称"] or "").strip(),
            description=(r.get("项目描述") or "").strip(),
            progress=progress,
            tractor_demand=0,
            trailer_demand=0,
            stage=int(r["_stage"]),
            owner=owner,
            owner_dept_id=dept_id,
            created_by=user.id,
        )
        db.add(p)
        db.flush()
        # 项目进展为导入必填项：同时写入第一条进展记录（与手工新建同一套规则）
        db.add(ProjectProgress(project_id=pid, content=progress, created_by=user.id))
    return len(rows)


def export_market_projects(db: Session, rows: list[MarketProject]) -> bytes:
    """导出市场项目清单。

    列与「项目管理」列表、编辑表单保持一致（业务列同名，另加项目ID与系统列），
    因此导出文件本身即可作为导入模板回灌。
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "项目列表"
    _write_banner(
        ws,
        len(MARKET_PROJECT_EXPORT_COLUMNS),
        "市场项目清单",
        [f"共 {len(rows)} 个项目", "带「系统」字样的列由系统生成，回灌导入时会被忽略"],
    )
    _style_header(ws, HEADER_ROW, MARKET_PROJECT_EXPORT_COLUMNS)

    user_names = {u.id: u.name for u in db.scalars(select(User)).all()}
    org_names = {o.id: o.name for o in db.scalars(select(Organization)).all()}
    for p in rows:
        ws.append(
            [
                p.id,
                p.name,
                p.progress or "",
                p.description or "",
                int(p.stage),
                p.owner,
                org_names.get(p.owner_dept_id or "", ""),
                int(p.tractor_demand or 0),
                int(p.trailer_demand or 0),
                user_names.get(p.created_by or "", ""),
                _fmt_dt(p.created_at.isoformat() if p.created_at else ""),
                _fmt_dt(p.updated_at.isoformat() if p.updated_at else ""),
            ]
        )
    if ws.max_row >= HEADER_ROW + 1:
        _style_data_rows(ws, HEADER_ROW + 1, ws.max_row, len(MARKET_PROJECT_EXPORT_COLUMNS), sample_rows=0)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
