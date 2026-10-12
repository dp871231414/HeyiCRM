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

from app.constants import TASK_ID_PREFIX
from app.models import MetricActual, MetricDef, Organization, Task, User

# ------------------------------------------------------------------ 模板列定义
#
# 列名与「任务管理」列表、编辑表单保持同一套叫法，避免同一字段多处异名：
#   列表/表单一律称「任务名称 / 任务分类 / 任务描述」，模板不再用「一级任务 / 二级任务」。

TASK_COLUMNS = [
    "任务名称",
    "任务分类",
    "任务描述",
    "是否异常",
    "目标",
    "已完成",
    "数量单位",
    "进展描述",
    "计划开始日期",
    "计划结束日期",
    "责任部门",
    "责任人",
]

# 可选列：老版本模板（无「数量单位」等）仍可导入，缺失时按空值处理
TASK_OPTIONAL_COLUMNS = {"任务分类", "任务描述", "数量单位", "进展描述", "是否异常"}

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
    ["进展描述", "选填。当前进展的补充说明"],
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


def import_tasks(db: Session, rows: list[dict], user: User) -> int:
    for r in rows:
        dept_raw = r["责任部门"]
        org = db.scalar(select(Organization).where(Organization.id == dept_raw))
        if not org:
            org = db.scalar(select(Organization).where(Organization.name == dept_raw))
        task = Task(
            id=next_task_id(db),
            parent=r["任务名称"],
            title=r.get("任务分类") or None,
            description=r.get("任务描述", ""),
            abnormal=r.get("是否异常") == "是",
            target=Decimal(str(r["目标"])),
            done=Decimal(str(r["已完成"])),
            unit=r.get("数量单位", ""),
            note=r.get("进展描述", ""),
            start_date=datetime.strptime(r["计划开始日期"], "%Y-%m-%d").date(),
            end_date=datetime.strptime(r["计划结束日期"], "%Y-%m-%d").date(),
            dept_id=org.id,
            owner=r["责任人"],
            created_by=user.id,
        )
        db.add(task)
        db.flush()
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
    for t in rows:
        d = task_to_dict(t)
        ws.append(
            [
                d["id"],
                d["parent"],
                d["title"] or "",
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
