"""达成率、红黄绿灯、回款、时间进度与任务健康度计算。

本模块为纯业务逻辑，与 Web 框架无关，可独立单测。
口径：
- 年度目标 / 项目公司目标按「年份」存一份（period='2026'），全年各月度周期共用；
- 完成值为「年初至今累计」（收入/消化/利润）或「期末快照」（运营车辆）；
- 回款率 = 累计回款 / 累计收入完成值；
- 时间进度 = 年初至数据截至日的天数 / 全年天数。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import MetricActual, MetricDef, MetricTarget

# ---------------------------------------------------------------- 时间口径


def reference_date() -> date:
    """业务判定的「今天」：优先取配置，否则取服务器当天。"""
    if settings.data_as_of:
        try:
            return datetime.strptime(settings.data_as_of, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def current_period() -> str:
    if settings.current_period:
        return settings.current_period
    return reference_date().strftime("%Y-%m")


def time_progress_of(period: str) -> float:
    """年度时间进度：当前周期按数据截至日，历史周期按该月月末。"""
    year, month = (int(x) for x in str(period).split("-")[:2])
    year_start = date(year, 1, 1)
    days_in_year = (date(year, 12, 31) - year_start).days + 1
    if period == current_period():
        as_of = reference_date()
    else:
        # 该月最后一天
        next_month = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        as_of = date.fromordinal(next_month.toordinal() - 1)
    return ((as_of - year_start).days + 1) / days_in_year


def vs_time_progress(rate: float | None, period: str) -> float | None:
    if rate is None:
        return None
    return rate - time_progress_of(period)


# ---------------------------------------------------------------- 取值索引


def _f(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@dataclass
class ValuesIndex:
    """目标值/实际值索引，键为 (metric_id, org_id, period)。"""

    targets: dict[tuple[str, str, str], float] = field(default_factory=dict)
    actuals: dict[tuple[str, str, str], float] = field(default_factory=dict)

    def target(self, metric_id: str, org_id: str, period: str) -> float | None:
        return self.targets.get((metric_id, org_id, str(period)))

    def actual(self, metric_id: str, org_id: str, period: str) -> float | None:
        return self.actuals.get((metric_id, org_id, str(period)))


def load_index(db: Session, org_ids: list[str] | None = None, periods: list[str] | None = None) -> ValuesIndex:
    idx = ValuesIndex()
    tq = select(MetricTarget.metric_id, MetricTarget.org_id, MetricTarget.period, MetricTarget.value)
    aq = select(MetricActual.metric_id, MetricActual.org_id, MetricActual.period, MetricActual.value)
    if org_ids:
        tq = tq.where(MetricTarget.org_id.in_(org_ids))
        aq = aq.where(MetricActual.org_id.in_(org_ids))
    if periods:
        tq = tq.where(MetricTarget.period.in_(periods))
        aq = aq.where(MetricActual.period.in_(periods))
    for mid, oid, period, value in db.execute(tq).all():
        idx.targets[(mid, oid, str(period))] = _f(value)
    for mid, oid, period, value in db.execute(aq).all():
        idx.actuals[(mid, oid, str(period))] = _f(value)
    return idx


# ---------------------------------------------------------------- 目标口径


def is_annual_target_def(def_: MetricDef | None) -> bool:
    return bool(def_ and def_.group in ("annual", "project"))


def target_period_of(def_: MetricDef | None, period: str) -> str:
    return str(period)[:4] if is_annual_target_def(def_) else str(period)


def resolve_target(def_: MetricDef | None, period: str, org_id: str, idx: ValuesIndex) -> float | None:
    exact = idx.target(def_.id, org_id, period)
    if exact is not None:
        return exact
    if not is_annual_target_def(def_):
        return None
    year = str(period)[:4]
    for (mid, oid, p), value in idx.targets.items():
        if mid == def_.id and oid == org_id and str(p)[:4] == year:
            return value
    return None


# ---------------------------------------------------------------- 达成率与灯


def calc_achievement(def_: MetricDef, target: float | None, actual: float | None) -> dict | None:
    """返回 {rate, gap, target, actual, is_zero_target} 或 None（无法判定）。"""
    if def_.no_target or target is None or actual is None:
        return None

    is_zero_target = def_.direction == "positive" and target == 0
    is_zero_actual = def_.direction == "negative" and actual == 0

    if is_zero_target:
        rate: float = 1.0 if actual == 0 else 0.0
    elif def_.direction == "positive":
        rate = actual / target
    else:
        rate = float("inf") if is_zero_actual else target / actual

    return {
        "rate": rate,
        "gap": actual - target,
        "target": target,
        "actual": actual,
        "is_zero_target": is_zero_target,
    }


def light_of(def_: MetricDef, target: float | None, actual: float | None) -> str:
    """红黄绿灯：直接比较实际值与目标值，不依赖达成率反推。"""
    if def_.no_target or target is None or actual is None:
        return "none"
    if def_.direction == "positive":
        # 零目标指标按绝对值判定：只能达标记满，出现任何超出即红灯
        if target == 0:
            return "green" if actual == 0 else "red"
        if actual >= target:
            return "green"
        warn = _f(def_.warn)
        if target > 0 and warn is not None and actual >= target * warn:
            return "amber"
        return "red"
    if actual <= target:
        return "green"
    danger = _f(def_.danger)
    tolerance = (danger if danger and danger > 1 else 1 + (danger or 0.1))
    if actual <= target * tolerance:
        return "amber"
    return "red"


# ---------------------------------------------------------------- 回款


def has_collection(defs_by_parent: dict[str, list[MetricDef]], metric_id: str) -> bool:
    return bool(defs_by_parent.get(metric_id))


def collection_rate(
    def_: MetricDef,
    coll_def: MetricDef,
    idx: ValuesIndex,
    period: str,
    org_id: str,
) -> dict | None:
    rev = idx.actual(def_.id, org_id, period)
    coll = idx.actual(coll_def.id, org_id, period)
    if rev is None or coll is None or rev == 0:
        return None
    rate_target = _f(def_.rate_target) or 0.95
    return {"rate": coll / rev, "coll": coll, "rateTarget": rate_target}


def collection_light(rate: float | None, rate_target: float) -> str:
    if rate is None:
        return "none"
    if rate >= rate_target:
        return "green"
    if rate >= rate_target - 0.05:
        return "amber"
    return "red"


# ---------------------------------------------------------------- 分组统计


def defs_by_group(db: Session, group: str) -> list[MetricDef]:
    return list(
        db.scalars(
            select(MetricDef)
            .where(MetricDef.group == group)
            .order_by(MetricDef.sort_order, MetricDef.id)
        ).all()
    )


def all_defs(db: Session) -> list[MetricDef]:
    return list(db.scalars(select(MetricDef).order_by(MetricDef.sort_order, MetricDef.id)).all())


def children_by_parent(defs: list[MetricDef]) -> dict[str, list[MetricDef]]:
    out: dict[str, list[MetricDef]] = {}
    for d in defs:
        if d.parent_id:
            out.setdefault(d.parent_id, []).append(d)
    return out


def group_metric_stats(
    db: Session,
    group: str,
    period: str,
    org_id: str,
    idx: ValuesIndex | None = None,
) -> dict:
    """维护页与驾驶舱共用同一份统计结果，保证口径一致。回款子指标并入主指标行。"""
    defs = defs_by_group(db, group)
    defs_all = all_defs(db)
    cb = children_by_parent(defs_all)
    idx = idx or load_index(db)
    rows = []
    for d in defs:
        if d.family == "collection":
            continue
        target = resolve_target(d, period, org_id, idx)
        actual = idx.actual(d.id, org_id, period)
        ach = calc_achievement(d, target, actual)
        coll_children = cb.get(d.id, [])
        coll_rate = None
        coll_light = None
        if coll_children:
            bundle = collection_rate(d, coll_children[0], idx, period, org_id)
            if bundle:
                coll_rate = bundle["rate"]
                coll_light = collection_light(bundle["rate"], bundle["rateTarget"])
        rows.append(
            {
                "def": d,
                "target": target,
                "actual": actual,
                "ach": ach,
                "light": light_of(d, target, actual),
                "collRate": coll_rate,
                "collLight": coll_light,
            }
        )
    counts = {
        "total": len(rows),
        "green": sum(1 for r in rows if r["light"] == "green"),
        "amber": sum(1 for r in rows if r["light"] == "amber"),
        "red": sum(1 for r in rows if r["light"] == "red"),
        "none": sum(1 for r in rows if r["light"] == "none"),
        "filled": sum(1 for r in rows if r["actual"] is not None),
    }
    return {"rows": rows, "counts": counts}


# ---------------------------------------------------------------- 任务计算


def calc_progress(target: float, done: float) -> int:
    if not target or target <= 0:
        return 0
    return round(done / target * 100)


def is_task_done(target: float, done: float) -> bool:
    return target > 0 and done >= target


def days_left(end_date: date, base: date | None = None) -> int:
    base = base or reference_date()
    return (end_date - base).days


def deadline_of(target: float, done: float, end_date: date, base: date | None = None) -> dict:
    progress = calc_progress(target, done)
    days = days_left(end_date, base)
    if is_task_done(target, done):
        return {"level": "done", "label": "已完成", "progress": progress, "days": days}
    if days < 0:
        return {"level": "overdue", "label": f"逾期 {abs(days)} 天", "progress": progress, "days": days}
    if days < 1:
        return {"level": "due_soon", "label": "临期", "progress": progress, "days": days}
    return {"level": "normal", "label": "正常", "progress": progress, "days": days}


def is_overdue(target: float, done: float, end_date: date, base: date | None = None) -> bool:
    return not is_task_done(target, done) and days_left(end_date, base) < 0


def task_health(target: float, done: float, end_date: date, abnormal: bool, base: date | None = None) -> dict:
    d = deadline_of(target, done, end_date, base)
    if abnormal and d["level"] not in ("done", "overdue"):
        return {**d, "level": "risk", "label": "异常"}
    return d


def task_to_dict(task) -> dict:
    """任务 ORM → 前端字典（含系统计算列）。"""
    target = _f(task.target) or 0.0
    done = _f(task.done) or 0.0
    health = task_health(target, done, task.end_date, bool(task.abnormal))
    return {
        "id": task.id,
        "parent": task.parent,
        "title": task.title,
        "description": task.description,
        "abnormal": bool(task.abnormal),
        "target": target,
        "done": done,
        "unit": task.unit,
        "note": task.note,
        "startDate": task.start_date.isoformat(),
        "endDate": task.end_date.isoformat(),
        "deptId": task.dept_id,
        "owner": task.owner,
        "progress": health["progress"],
        "daysLeft": health["days"],
        "statusLevel": health["level"],
        "statusLabel": health["label"],
    }
