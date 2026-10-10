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
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import TASK_ID_PREFIX
from app.models import MetricActual, MetricDef, Organization, Task, User

# ------------------------------------------------------------------ 模板列定义

TASK_COLUMNS = [
    "一级任务",
    "二级任务",
    "描述",
    "是否异常",
    "目标",
    "已完成",
    "进展描述",
    "计划开始日期",
    "计划结束日期",
    "责任部门",
    "责任人",
]

METRIC_COLUMNS = ["指标编码", "指标名称", "统计周期", "统计组织", "实际值"]

_HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_NOTE_FILL = PatternFill("solid", fgColor="FFF2CC")
_BORDER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)


class RowError(dict):
    pass


def _style_header(ws, columns: list[str]) -> None:
    ws.append(columns)
    for idx in range(1, len(columns) + 1):
        cell = ws.cell(row=1, column=idx)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _BORDER_ALIGN
        ws.column_dimensions[get_column_letter(idx)].width = max(14, len(columns[idx - 1]) * 2 + 6)


def _safe_sheet_name(wb: Workbook, name: str) -> str:
    used = {ws.title for ws in wb.worksheets}
    if name not in used:
        return name
    i = 1
    while f"{name}{i}" in used:
        i += 1
    return f"{name}{i}"


# ------------------------------------------------------------------ 模板生成


def build_task_template(db: Session) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "任务数据"
    _style_header(ws, TASK_COLUMNS)
    ws.append(
        [
            "完成全年营收目标 10.2 亿",
            "华东大区营收达成",
            "华东大区年度营收承接",
            "否",
            46000,
            31800,
            "Q3 累计 3.18 亿",
            "2026-01-01",
            "2026-12-31",
            "市场部",
            "郑凯",
        ]
    )

    # 说明
    notes = wb.create_sheet("填写说明")
    for row in [
        ["填写项", "说明"],
        ["一级任务", "必填。公司级重点任务标题；一级任务相同的多行自动归组为同一任务"],
        ["二级任务", "选填。部门/班组级承接任务，可为空"],
        ["是否异常", "选填，只能填「是」或「否」，默认否"],
        ["目标", "必填。数字，非量化任务填 1"],
        ["已完成", "必填。数字，非量化任务未完成填 0、完成填 1"],
        ["计划开始日期", "必填，格式 2026-10-01"],
        ["计划结束日期", "必填，格式 2026-12-31，不能早于开始日期"],
        ["责任部门", "必填。组织名称或编码（见「组织清单」页）"],
        ["责任人", "必填。必须是系统内已有账号姓名"],
        ["完成进度 / 临期逾期", "由系统自动计算，不在模板中填写"],
    ]:
        notes.append(row)
        if len(row) == 2 and row[0] in ("填写项",):
            notes.cell(row=notes.max_row, column=1).font = Font(bold=True)
    notes.column_dimensions["A"].width = 20
    notes.column_dimensions["B"].width = 70

    # 组织清单
    orgs = wb.create_sheet("组织清单")
    orgs.append(["编码", "名称"])
    for o in db.scalars(select(Organization).order_by(Organization.sort_order, Organization.id)).all():
        orgs.append([o.id, o.name])

    # 数据验证：是否异常
    dv_abn = DataValidation(type="list", formula1='"是,否"', allow_blank=True)
    dv_abn.error = "只能填「是」或「否」"
    ws.add_data_validation(dv_abn)
    dv_abn.add(f"D2:D{max(2, 2000)}")

    # 数据验证：责任部门（引用组织清单）
    dv_dept = DataValidation(type="list", formula1="=组织清单!$B$2:$B$200", allow_blank=True)
    dv_dept.error = "责任部门需存在于组织清单"
    ws.add_data_validation(dv_dept)
    dv_dept.add(f"J2:J{max(2, 2000)}")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_metric_template(db: Session) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "指标数据"
    _style_header(ws, METRIC_COLUMNS)
    ws.append(["REV_SALE", "销售收入", "2026-10", "CO", 9860])

    notes = wb.create_sheet("填写说明")
    for row in [
        ["填写项", "说明"],
        ["指标编码", "必填。见「指标清单」页"],
        ["指标名称", "选填，仅供人工核对，导入以编码为准"],
        ["统计周期", "必填。格式 2026-10，须与看板当前周期一致"],
        ["统计组织", "必填。组织编码，如 CO / PC1"],
        ["实际值", "必填。纯数字，不带单位"],
    ]:
        notes.append(row)
        if row[0] == "填写项":
            notes.cell(row=notes.max_row, column=1).font = Font(bold=True)
    notes.column_dimensions["A"].width = 20
    notes.column_dimensions["B"].width = 70

    metrics = wb.create_sheet("指标清单")
    metrics.append(["指标编码", "指标名称", "单位", "所属组", "统计组织"])
    for m in db.scalars(select(MetricDef).order_by(MetricDef.sort_order, MetricDef.id)).all():
        scope_hint = "CO / PC1-PCn" if m.group in ("annual", "project") else "CO"
        metrics.append([m.id, m.name, m.unit, m.group, scope_hint])

    dv_metric = DataValidation(type="list", formula1="=指标清单!$A$2:$A$200", allow_blank=True)
    dv_metric.error = "指标编码需存在于指标清单"
    ws.add_data_validation(dv_metric)
    dv_metric.add(f"A2:A{max(2, 2000)}")

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


def parse_rows(file_bytes: bytes, columns: list[str], max_rows: int) -> list[dict]:
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.worksheets[0]
    header = [_cell_str(c.value) for c in ws[1]]
    # 按列名定位（顺序无关），缺失列报错
    index = {name: header.index(name) for name in columns if name in header}
    missing = [c for c in columns if c not in index]
    if missing:
        raise ValueError(f"模板缺少列：{'、'.join(missing)}")

    rows: list[dict] = []
    for r in ws.iter_rows(min_row=2, values_only=True):
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

        if not r.get("一级任务"):
            row_errors.append({"field": "一级任务", "msg": "不能为空"})

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
            parent=r["一级任务"],
            title=r.get("二级任务") or None,
            description=r.get("描述", ""),
            abnormal=r.get("是否异常") == "是",
            target=Decimal(str(r["目标"])),
            done=Decimal(str(r["已完成"])),
            unit=r.get("单位", ""),
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


def export_tasks(rows: list[Task]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "任务列表"
    columns = TASK_COLUMNS + ["完成进度", "状态"]
    _style_header(ws, columns)
    from app.services.achievement import _f, task_to_dict

    for t in rows:
        d = task_to_dict(t)
        ws.append(
            [
                d["parent"],
                d["title"] or "",
                d["description"],
                "是" if d["abnormal"] else "否",
                d["target"],
                d["done"],
                d["note"],
                d["startDate"],
                d["endDate"],
                d["deptId"],
                d["owner"],
                f"{d['progress']}%",
                d["statusLabel"],
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
