"""经营驾驶舱路由：分析总结、总览、指标趋势。

**权限口径（重要）**：本模块只按**角色权限**判断能否使用，不做数据范围（可见范围）校验 ——
有 `dashboard.view` 即视为可查看经营分析数据。「全公司与项目公司不是递归汇总关系」
（项目公司只承载运营收入，销售收入来自系统中的其他主体），若按可见范围裁剪，
部门范围账号反而看不到完整的经营口径，容易被误读。

数据范围（scope）**仅用于任务模块**，见 `api/v1/tasks.py`。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_perm
from app.db.session import get_db
from app.models import MetricActual, MetricDef, Organization, User
from app.schemas.task import DeptTaskStat
from app.services.achievement import current_period, group_metric_stats, load_index
from app.services.summary import build_summary

router = APIRouter(prefix="/dashboard", tags=["经营驾驶舱"])


@router.get("/summary")
def summary(period: str = "", org_id: str = "CO", db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view"))):
    period = period or current_period()
    if not db.get(Organization, org_id):
        raise HTTPException(status_code=404, detail="组织不存在")
    return build_summary(db, period, org_id)


@router.get("/overview")
def overview(period: str = "", org_id: str = "CO", db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view"))):
    period = period or current_period()
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    from app.api.v1.metrics import build_board

    # 不传可见组织：驾驶舱按全公司口径取数（数据范围不影响本模块）
    board = build_board(db, period, org_id)

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
    }


@router.get("/dept-task-stats", response_model=list[DeptTaskStat])
def dept_task_stats(
    period: str = "",
    filter: str = "all",
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("dashboard.view")),
):
    """部门任务完成度（驾驶舱）· 支持按创建时间筛选，独立于总览单独取数。

    之所以不挂在 `/overview` 上：切换筛选只要重算一次 GROUP BY，
    没必要连带重建整套指标看板；而首屏是与 summary / overview 并发取的，不增加往返。

    `filter`：`all` 全部（默认）/ `year` 本年新增 / `month` 当月新增 / `open` 未结束；
    年月均取 `period`（页面顶部统计周期）所在年月，未识别的取值按「全部」处理。
    """
    from app.api.v1.tasks import dept_stats_all, dept_task_filter

    if filter not in ("all", "year", "month", "open"):
        filter = "all"
    return dept_stats_all(db, task_filter=dept_task_filter(period or current_period(), filter))


@router.get("/metrics/{metric_id}/trend")
def trend(metric_id: str, org_id: str = "CO", db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view"))):
    d = db.get(MetricDef, metric_id)
    if not d:
        raise HTTPException(status_code=404, detail="指标不存在")
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
