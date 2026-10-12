"""经营驾驶舱路由：分析总结、总览、指标趋势。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_perm
from app.db.session import get_db
from app.models import MetricActual, MetricDef, Organization, Task, User
from app.services import scope as scope_svc
from app.services.achievement import current_period, group_metric_stats, load_index
from app.services.summary import build_summary

router = APIRouter(prefix="/dashboard", tags=["经营驾驶舱"])


@router.get("/summary")
def summary(period: str = "", org_id: str = "CO", db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view"))):
    period = period or current_period()
    if not db.get(Organization, org_id):
        raise HTTPException(status_code=404, detail="组织不存在")
    if not scope_svc.org_in_scope(db, user, org_id):
        raise HTTPException(status_code=403, detail="无权查看该组织的数据")
    return build_summary(db, period, org_id, user)


@router.get("/overview")
def overview(period: str = "", org_id: str = "CO", db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view"))):
    period = period or current_period()
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not scope_svc.org_in_scope(db, user, org_id):
        raise HTTPException(status_code=403, detail="无权查看该组织的数据")

    from app.api.v1.metrics import build_board
    from app.api.v1.tasks import dept_stats

    board = build_board(db, period, org_id, scope_svc.visible_org_ids(db, user))
    stats = dept_stats(db=db, user=user)

    return {
        "period": period,
        "orgId": org_id,
        "orgName": org.name,
        "orgType": org.type,
        "timeProgress": board["timeProgress"],
        "annual": board["annual"],
        "monitor": board["monitor"] if org.type == "company" else [],
        "projectCompare": board["project"]["companies"] if org.type in ("company", "project") else [],
        "projectMetrics": board["project"]["metrics"],
        "counts": board["counts"],
        "deptTaskStats": stats,
    }


@router.get("/metrics/{metric_id}/trend")
def trend(metric_id: str, org_id: str = "CO", db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view"))):
    d = db.get(MetricDef, metric_id)
    if not d:
        raise HTTPException(status_code=404, detail="指标不存在")
    if not scope_svc.org_in_scope(db, user, org_id):
        raise HTTPException(status_code=403, detail="无权查看该组织的数据")
    rows = db.execute(
        select(MetricActual.period, MetricActual.value)
        .where(MetricActual.metric_id == metric_id, MetricActual.org_id == org_id)
        .order_by(MetricActual.period)
    ).all()
    return {
        "metricId": metric_id,
        "name": d.name,
        "unit": d.unit,
        "direction": d.direction,
        "points": [{"period": str(p), "value": float(v)} for p, v in rows],
    }


@router.get("/metrics/trends")
def trends(
    ids: str = "",
    org_id: str = "CO",
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("dashboard.view")),
):
    """批量取多个指标的趋势（一次请求代替 N 次）。

    指标维护页原先为每个监控指标各发一个 trend 请求。在单次往返约 300ms 的环境下，
    10 个并发会互相争抢（实测尾请求 TTFB 被拖到 2.4 秒），而表格又必须等全部返回。
    合并成一次请求后只剩一个往返，且只查一次库。
    """
    metric_ids = [i.strip() for i in ids.split(",") if i.strip()]
    if not metric_ids:
        return {"series": []}
    if not scope_svc.org_in_scope(db, user, org_id):
        raise HTTPException(status_code=403, detail="无权查看该组织的数据")

    defs = {d.id: d for d in db.scalars(select(MetricDef).where(MetricDef.id.in_(metric_ids))).all()}
    rows = db.execute(
        select(MetricActual.metric_id, MetricActual.period, MetricActual.value)
        .where(MetricActual.metric_id.in_(metric_ids), MetricActual.org_id == org_id)
        .order_by(MetricActual.metric_id, MetricActual.period)
    ).all()
    grouped: dict[str, list[dict]] = {}
    for mid, period, value in rows:
        grouped.setdefault(mid, []).append({"period": str(period), "value": float(value)})

    series = []
    for mid in metric_ids:  # 保持调用方给定的顺序
        d = defs.get(mid)
        if not d:
            continue
        series.append(
            {
                "metricId": mid,
                "name": d.name,
                "unit": d.unit,
                "direction": d.direction,
                "points": grouped.get(mid, []),
            }
        )
    return {"series": series}
