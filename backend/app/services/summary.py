"""规则生成分析总结 · 确定性模板拼装，不引入 AI。

结构：整体结论 → 亮点 → 风险（指标 / 监控 / 任务）→ 建议。

**权限口径**：本模块服务于经营驾驶舱，只按角色权限开放，不做数据范围（可见范围）过滤
—— 其中的任务统计同样按全量口径参与经营分析。数据范围仅用于任务模块本身。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MetricDef, Organization, Task
from app.services.achievement import (
    _f,
    calc_achievement,
    collection_light,
    collection_rate,
    children_by_parent,
    defs_by_group,
    all_defs,
    group_metric_stats,
    load_index,
    progress_tone,
    TONE_LABEL,
    reference_date,
    resolve_target,
    task_health,
    time_progress_of,
    vs_time_progress,
)
from app.constants import ORG_TYPE_COMPANY, ORG_TYPE_PROJECT


def _prev_period(period: str) -> str | None:
    try:
        year, month = (int(x) for x in str(period).split("-")[:2])
    except ValueError:
        return None
    if month <= 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _org_name(db: Session, org_id: str | None) -> str:
    if not org_id:
        return "—"
    org = db.get(Organization, org_id)
    return org.name if org else "—"


def _fmt(value, unit: str = "", digits: int | None = None) -> str:
    if value is None:
        return "—"
    if digits is None:
        digits = 0 if float(value).is_integer() else 2
    return f"{float(value):.{digits}f}"


def _fmt_pct(rate: float | None) -> str:
    if rate is None:
        return "—"
    if rate == float("inf"):
        return "∞"
    return f"{rate * 100:.1f}%"


def _metric_sentence(def_: MetricDef, ach: dict, trend: dict | None, period: str) -> str:
    # 与卡片徽章同一口径：进度状态（达成率 ÷ 时间进度），而不是「实际 vs 目标」
    status = TONE_LABEL[progress_tone(ach["rate"], time_progress_of(period))]
    light_text = status
    s = (
        f"{def_.name}实际 {_fmt(ach['actual'])} {def_.unit}，"
        f"目标 {_fmt(ach['target'])} {def_.unit}，达成率 {_fmt_pct(ach['rate'])}，{light_text}"
    )
    if def_.direction == "positive":
        s += f"，超目标 {_fmt(ach['gap'])} {def_.unit}" if ach["gap"] >= 0 else f"，缺口 {_fmt(abs(ach['gap']))} {def_.unit}"
    else:
        s += f"，优于目标 {_fmt(abs(ach['gap']))} {def_.unit}" if ach["gap"] <= 0 else f"，超出目标 {_fmt(ach['gap'])} {def_.unit}"
    if trend and trend.get("delta") is not None:
        direction = "上升" if trend["delta"] >= 0 else "下降"
        s += f"；较{trend['prevLabel']}{direction} {_fmt_pct(abs(trend['delta']))}"
    return s


def _task_sentence(task: Task) -> str:
    target = _f(task.target) or 0.0
    done = _f(task.done) or 0.0
    h = task_health(target, done, task.end_date, bool(task.abnormal))
    title = f"{task.parent} / {task.title}" if task.parent and task.title and task.title != task.parent else (task.title or task.parent)
    s = f"{title}：完成进度 {h['progress']}%（{_fmt(done)} / {_fmt(target)} {task.unit}），{h['label']}"
    if task.abnormal and h["level"] != "done":
        s += "，人工标记为异常"
    return s


def _trend_for(db: Session, def_: MetricDef, period: str, org_id: str, idx) -> dict:
    prev = _prev_period(period)
    if not prev:
        return {"delta": None, "prev": None, "cur": None, "prevLabel": "上期"}
    cur = idx.actual(def_.id, org_id, period)
    old = idx.actual(def_.id, org_id, prev)
    label = f"{prev.split('-')[1]}月"
    if cur is None or old is None or old == 0:
        return {"delta": None, "prev": old, "cur": cur, "prevLabel": label}
    delta = (cur - old) / abs(old)
    is_good = delta < 0 if def_.direction == "negative" else delta > 0
    return {"delta": delta, "prev": old, "cur": cur, "prevLabel": label, "isGood": is_good}


def build_summary(db: Session, period: str, org_id: str) -> dict:
    idx = load_index(db)
    group = "project" if _is_project(db, org_id) else "annual"
    defs_all = all_defs(db)
    cb = children_by_parent(defs_all)

    metrics = []
    for d in defs_by_group(db, group):
        if not d.weight or d.weight <= 0:
            continue
        target = resolve_target(d, period, org_id, idx)
        if target is None:
            continue
        actual = idx.actual(d.id, org_id, period)
        ach = calc_achievement(d, target, actual)
        if ach:
            metrics.append({"def": d, "ach": ach})

    group_stats = group_metric_stats(db, group, period, org_id, idx)

    if not metrics:
        return {
            "headline": "本周期暂无指标数据",
            "verdict": "none",
            "weighted": None,
            "timeProgress": time_progress_of(period),
            "vsTime": None,
            "counts": group_stats["counts"],
            "points": [],
            "risks": [],
            "wins": [],
        }

    total_w = sum(x["def"].weight for x in metrics)
    weighted = sum(x["ach"]["rate"] * x["def"].weight for x in metrics) / total_w

    tp = time_progress_of(period)
    # 与卡片徽章同源：单指标状态一律按「达成率 ÷ 时间进度」分档（见 progress_tone）。
    # 用同一口径才能保证汇总统计、亮点、风险与卡片标签互不矛盾。
    by_tone: dict[str, list[dict]] = {"done": [], "ahead": [], "near": [], "risk": []}
    for x in metrics:
        by_tone[progress_tone(x["ach"]["rate"], tp)].append(x)
    done, lead, slow, lag = by_tone["done"], by_tone["ahead"], by_tone["near"], by_tone["risk"]

    # 整体结论：**用与单指标完全相同的判定**（progress_tone，达成率 ÷ 时间进度），
    # 阈值也一致 —— ≥1 良好 / 0.7 ~ <1 需关注 / <0.7 存在风险。
    # 原先按绝对值判（加权达成率 < 0.9 → 存在风险），对年度目标不成立：
    # 年中看 83.8% 会被判成「低于时间轴」，而它其实跑赢了 78.4% 的时间进度。
    verdict = {
        "done": "good",
        "ahead": "good",
        "near": "warn",
        "risk": "bad",
        "none": "none",
    }[progress_tone(weighted, tp)]

    verdict_text = {
        "good": "整体跑赢年度时间进度，目标可控",
        "warn": "整体略慢于年度时间进度，存在局部缺口需关注",
        "bad": "整体明显滞后于年度时间进度，存在明确风险需立即干预",
        "none": "暂无数据",
    }[verdict]

    vs = vs_time_progress(weighted, period)
    if vs is None:
        vs_text = "—"
    else:
        vs_text = f"跑赢年度时间进度 {_fmt_pct(abs(vs))}" if vs >= 0 else f"落后年度时间进度 {_fmt_pct(abs(vs))}"

    headline = (
        f"{period.replace('-', '年')}月综合加权达成率 {_fmt_pct(weighted)}，{verdict_text}。"
        f"共 {len(metrics)} 项指标，其中已达成 {len(done)} 项、领先 {len(lead)} 项、"
        f"偏慢 {len(slow)} 项、滞后 {len(lag)} 项。"
        f"年度时间进度 {_fmt_pct(tp)}，{vs_text}。"
    )

    wins = []
    for x in done[:3]:
        wins.append(_metric_sentence(x["def"], x["ach"], _trend_for(db, x["def"], period, org_id, idx), period))

    risks: list[dict] = []
    for x in lag:
        risks.append(
            {
                "type": "indicator",
                "org": org_id,
                "text": _metric_sentence(x["def"], x["ach"], _trend_for(db, x["def"], period, org_id, idx), period),
            }
        )
    for x in slow:
        t = _trend_for(db, x["def"], period, org_id, idx)
        if t.get("delta") is not None and (
            (x["def"].direction == "positive" and t["delta"] < 0) or (x["def"].direction == "negative" and t["delta"] > 0)
        ):
            risks.append(
                {
                    "type": "indicator",
                    "org": org_id,
                    "text": f"{x['def'].name}环比走弱，{_metric_sentence(x['def'], x['ach'], t, period)}",
                }
            )

    # 监控指标闭环提示（仅公司视角）
    if _is_company(db, org_id):
        inc_doing = idx.actual("INC_DOING", org_id, period)
        inc_tot = idx.actual("INC_TOT", org_id, period)
        if inc_doing is not None and inc_doing > 0:
            risks.append({"type": "monitor", "org": org_id, "text": f"本期共 {_fmt(inc_tot) if inc_tot is not None else '—'} 起事故，其中 {_fmt(inc_doing)} 起仍在处理中，需跟进闭环进度。"})
        fau_doing = idx.actual("FAU_DOING", org_id, period)
        fau_tot = idx.actual("FAU_TOT", org_id, period)
        if fau_doing is not None and fau_doing > 0:
            risks.append({"type": "monitor", "org": org_id, "text": f"本期共 {_fmt(fau_tot) if fau_tot is not None else '—'} 起车辆故障，其中 {_fmt(fau_doing)} 起未修复完成，需关注车辆可用率。"})

    # 任务侧：按全量口径统计（驾驶舱不做数据范围过滤，与页面口径一致）
    year = str(period)[:4]
    tq = select(Task).where(Task.end_date >= date(int(year), 1, 1), Task.end_date <= date(int(year), 12, 31))
    tasks = list(db.scalars(tq).all())
    health = [{"t": t, "h": task_health(_f(t.target) or 0.0, _f(t.done) or 0.0, t.end_date, bool(t.abnormal))} for t in tasks]
    overdue = [x for x in health if x["h"]["level"] == "overdue"]
    due_soon = [x for x in health if x["h"]["level"] == "due_soon"]
    abnormal = [x for x in health if x["t"].abnormal and x["h"]["level"] != "done"]

    seen: set[str] = set()
    for x in overdue + due_soon + abnormal:
        if x["t"].id in seen:
            continue
        seen.add(x["t"].id)
        risks.append({"type": "task", "org": x["t"].dept_id, "text": _task_sentence(x["t"]) + f"。{x['t'].note or ''}"})

    points = []
    if lag:
        worst = sorted(lag, key=lambda x: x["ach"]["rate"])[0]
        points.append(
            f"优先处理「{worst['def'].name}」（进度滞后），缺口 {_fmt(abs(worst['ach']['gap']))} {worst['def'].unit}，"
            f"建议由 {_org_name(db, worst['def'].owner_org_id)}牵头分析原因并给出改进计划。"
        )
    elif slow:
        points.append(f"{len(slow)} 项指标进度偏慢（低于年度时间进度），建议关注承接节奏，避免累积为缺口。")
    if overdue:
        points.append(f"{len(overdue)} 项任务已逾期，建议在最近一次经营会上逐项过堂，明确补救计划与新的完成时点。")
    if abnormal:
        points.append(f"{len(abnormal)} 项任务被标记为异常，建议要求责任人说明原因与恢复计划。")
    if due_soon:
        points.append(f"{len(due_soon)} 项任务今天到期，建议当天跟进确认能否按期完成。")
    if not risks:
        points.append("本周期未发现重大风险，建议保持现有执行节奏，并关注下期目标承接情况。")

    return {
        "headline": headline,
        "verdict": verdict,
        "weighted": weighted,
        "timeProgress": tp,
        "vsTime": vs,
        "counts": group_stats["counts"],
        "points": points,
        "risks": risks[:8],
        "wins": wins,
    }


def _is_project(db: Session, org_id: str) -> bool:
    org = db.get(Organization, org_id)
    return bool(org and org.type == ORG_TYPE_PROJECT)


def _is_company(db: Session, org_id: str) -> bool:
    org = db.get(Organization, org_id)
    return bool(org and org.type == ORG_TYPE_COMPANY)
