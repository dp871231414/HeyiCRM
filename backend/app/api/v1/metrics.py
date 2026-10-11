"""指标路由：定义 / 周期 / 维护看板 / 目标与累计完成值录入 / 导入。"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ORG_TYPE_COMPANY, ORG_TYPE_PROJECT
from app.core.deps import get_user_perms, require_perm
from app.db.session import get_db
from app.models import MetricActual, MetricDef, MetricTarget, Organization, User
from app.schemas.common import ImportResult
from app.schemas.metric import MetricValueIn
from app.services import scope as scope_svc
from app.services.achievement import (
    _f,
    all_defs,
    calc_achievement,
    children_by_parent,
    collection_light,
    collection_rate,
    current_period,
    defs_by_group,
    group_metric_stats,
    light_of,
    load_index,
    reference_date,
    resolve_target,
    target_period_of,
    time_progress_of,
)
from app.services.audit import write_log
from app.services.importer import (
    build_metric_template,
    import_metrics,
    parse_rows,
    validate_metric_rows,
)
from app.services.serializers import org_name


router = APIRouter(prefix="/metrics", tags=["指标"])


def _owner(db: Session, org_id: str | None) -> str:
    return org_name(db, org_id)


def fmt_rate(rate: float | None) -> str:
    if rate is None:
        return "—"
    if rate == float("inf"):
        return "∞"
    return f"{rate * 100:.1f}%"


def build_row(def_: MetricDef, target, actual, idx, period: str, org_id: str, coll_defs) -> dict:
    ach = calc_achievement(def_, target, actual)
    lig = light_of(def_, target, actual)
    row = {
        "metricId": def_.id,
        "name": def_.name,
        "unit": def_.unit,
        "group": def_.group,
        "family": def_.family,
        "direction": def_.direction,
        "weight": def_.weight,
        "snapshot": bool(def_.is_snapshot),
        "noTarget": bool(def_.no_target),
        "ownerOrgId": def_.owner_org_id,
        "ownerOrgName": "",
        "description": def_.description,
        "target": target,
        "actual": actual,
        "rate": ach["rate"] if ach else None,
        "rateText": fmt_rate(ach["rate"]) if ach else "—",
        "light": lig,
        "gap": ach["gap"] if ach else None,
        "hasCollection": bool(coll_defs.get(def_.id)),
        "collMetricId": coll_defs[def_.id][0].id if coll_defs.get(def_.id) else None,
        "collActual": None,
        "collRate": None,
        "collLight": "none",
        "vsTime": (ach["rate"] - time_progress_of(period)) if ach else None,
        "periodLabel": "年度" if def_.group in ("annual", "project") else period,
    }
    if coll_defs.get(def_.id):
        bundle = collection_rate(def_, coll_defs[def_.id][0], idx, period, org_id)
        if bundle:
            row["collActual"] = bundle["coll"]
            row["collRate"] = bundle["rate"]
            row["collLight"] = collection_light(bundle["rate"], bundle["rateTarget"])
    return row


def build_board(db: Session, period: str, org_id: str, visible_orgs: list[str] | None = None) -> dict:
    """组织看板数据 · 全部按视角组织取数。

    指标目标只下达在公司与项目公司层级（见原型 `primaryMetricGroup`），
    因此部门/班组视角的指标数据为空，由前端给出说明性空态；
    写入授权另见 board 接口（仅全公司数据可见范围可在全公司视角维护）。
    """
    company_org = org_id
    idx = load_index(db)
    defs = all_defs(db)
    coll_defs = children_by_parent(defs)
    cb = {k: v for k, v in coll_defs.items()}

    annual = []
    for d in defs_by_group(db, "annual"):
        if d.family == "collection":
            continue
        target = resolve_target(d, period, company_org, idx)
        actual = idx.actual(d.id, company_org, period)
        row = build_row(d, target, actual, idx, period, company_org, cb)
        row["ownerOrgName"] = _owner(db, d.owner_org_id)
        annual.append(row)

    monitor = []
    for d in defs_by_group(db, "monitor"):
        target = resolve_target(d, period, company_org, idx)
        actual = idx.actual(d.id, company_org, period)
        row = build_row(d, target, actual, idx, period, company_org, cb)
        row["ownerOrgName"] = _owner(db, d.owner_org_id)
        monitor.append(row)

    # 项目公司模块 · 仅列出调用方可见范围内的项目公司（数据隔离）
    projects = db.scalars(
        select(Organization).where(Organization.type == ORG_TYPE_PROJECT).order_by(Organization.id)
    ).all()
    if visible_orgs is not None:
        projects = [o for o in projects if o.id in visible_orgs]
    proj_defs = [d for d in defs_by_group(db, "project") if d.family != "collection"]
    companies = []
    for org in projects:
        cells = []
        rates = []
        filled = 0
        for d in proj_defs:
            target = resolve_target(d, period, org.id, idx)
            actual = idx.actual(d.id, org.id, period)
            row = build_row(d, target, actual, idx, period, org.id, cb)
            row["ownerOrgName"] = _owner(db, d.owner_org_id)
            cells.append(row)
            if row["rate"] is not None:
                rates.append(row["rate"])
            if actual is not None:
                filled += 1
        companies.append(
            {
                "orgId": org.id,
                "name": org.name,
                "head": org.head,
                "cells": cells,
                "completion": (sum(rates) / len(rates)) if rates else None,
                "filled": filled,
                "total": len(proj_defs),
            }
        )

    annual_counts = group_metric_stats(db, "annual", period, company_org, idx)["counts"]

    return {
        "period": period,
        "currentPeriod": current_period(),
        "dataAsOf": reference_date().isoformat(),
        "timeProgress": time_progress_of(period),
        "orgId": org_id,
        "orgType": db.get(Organization, org_id).type if db.get(Organization, org_id) else "",
        "annual": annual,
        "monitor": monitor,
        "project": {"companies": companies, "metrics": [{"id": d.id, "name": d.name, "unit": d.unit, "snapshot": bool(d.is_snapshot)} for d in proj_defs]},
        "counts": annual_counts,
    }


@router.get("/defs")
def metric_defs(group: str = "", db: Session = Depends(get_db), user: User = Depends(require_perm("metric.view"))):
    defs = defs_by_group(db, group) if group else all_defs(db)
    return [
        {
            "id": d.id,
            "name": d.name,
            "unit": d.unit,
            "group": d.group,
            "family": d.family,
            "parentId": d.parent_id,
            "direction": d.direction,
            "cycle": d.cycle,
            "weight": d.weight,
            "warn": _f(d.warn),
            "danger": _f(d.danger),
            "rateTarget": _f(d.rate_target),
            "snapshot": bool(d.is_snapshot),
            "noTarget": bool(d.no_target),
            "ownerOrgId": d.owner_org_id,
            "ownerOrgName": _owner(db, d.owner_org_id),
            "description": d.description,
        }
        for d in defs
    ]


@router.get("/periods")
def periods(db: Session = Depends(get_db), user: User = Depends(require_perm("metric.view"))):
    rows = db.scalars(select(MetricActual.period).distinct()).all()
    periods_set = sorted({str(p) for p in rows if "-" in str(p)})
    return {
        "current": current_period(),
        "dataAsOf": reference_date().isoformat(),
        "periods": periods_set or [current_period()],
    }


@router.get("/board")
def board(period: str = "", org_id: str = "CO", db: Session = Depends(get_db), user: User = Depends(require_perm("metric.view"))):
    period = period or current_period()
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not scope_svc.org_in_scope(db, user, org_id):
        raise HTTPException(status_code=403, detail="无权查看该组织的数据")
    visible = scope_svc.visible_org_ids(db, user)
    data = build_board(db, period, org_id, visible)
    # 维护范围完全由权限决定，与角色属性（含默认可见范围）无关：
    #   metric.edit           —— 可录入 / 修改指标
    #   metric.edit_company   —— 可维护公司整体目标与监控指标
    #   metric.edit_project   —— 可维护项目公司指标
    # 权限决定「能否改」，可见范围决定「改哪些」——后者属数据隔离，不是操作门槛。
    perms = get_user_perms(db, user)
    can_edit = "metric.edit" in perms
    can_company = "metric.edit_company" in perms
    can_project = "metric.edit_project" in perms
    data["canEditAll"] = can_edit and can_company and org.type == ORG_TYPE_COMPANY
    all_projects = [o.id for o in db.scalars(select(Organization).where(Organization.type == ORG_TYPE_PROJECT)).all()]
    data["editableProjects"] = (
        [pid for pid in all_projects if pid in visible] if (can_edit and can_project) else []
    )
    data["perms"] = {
        "edit": can_edit,
        "editCompany": can_company,
        "editProject": can_project,
    }
    return data


def _upsert(db: Session, model, metric_id: str, org_id: str, period: str, value: float | None, user: User):
    existing = db.scalar(
        select(model).where(model.metric_id == metric_id, model.org_id == org_id, model.period == period)
    )
    if value is None:
        if existing:
            db.delete(existing)
        return
    if existing:
        existing.value = Decimal(str(value))
        if hasattr(existing, "created_by"):
            existing.created_by = user.id
    else:
        kwargs = {"metric_id": metric_id, "org_id": org_id, "period": period, "value": Decimal(str(value))}
        if model is MetricActual:
            kwargs["created_by"] = user.id
        db.add(model(**kwargs))


def _validate_write(db: Session, payload: MetricValueIn, user: User, perm: str) -> MetricDef:
    if perm not in get_user_perms(db, user):
        raise HTTPException(status_code=403, detail="无此操作权限")
    d = db.get(MetricDef, payload.metric_id)
    if not d:
        raise HTTPException(status_code=404, detail="指标不存在")
    if d.no_target and d.group == "monitor":
        pass  # 监控指标只能录累计完成值
    org = db.get(Organization, payload.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not scope_svc.org_in_scope(db, user, payload.org_id):
        raise HTTPException(status_code=403, detail="无权修改该组织的数据")
    return d


@router.put("/targets")
def put_target(payload: MetricValueIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_perm("metric.edit"))):
    d = _validate_write(db, payload, user, "metric.edit")
    if d.no_target:
        raise HTTPException(status_code=422, detail="监控指标无目标值")
    period = target_period_of(d, payload.period)
    _upsert(db, MetricTarget, payload.metric_id, payload.org_id, period, payload.value, user)
    write_log(db, user, "metric_target", "metric", payload.metric_id, {"org": payload.org_id, "period": period, "value": payload.value}, request)
    db.commit()
    return {"ok": True, "msg": "已保存", "data": {"period": period}}


@router.put("/actuals")
def put_actual(payload: MetricValueIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_perm("metric.edit"))):
    d = _validate_write(db, payload, user, "metric.edit")
    _upsert(db, MetricActual, payload.metric_id, payload.org_id, payload.period, payload.value, user)
    write_log(db, user, "metric_actual", "metric", payload.metric_id, {"org": payload.org_id, "period": payload.period, "value": payload.value}, request)
    db.commit()
    return {"ok": True, "msg": "已保存"}


@router.get("/import/template")
def metric_template(db: Session = Depends(get_db), user: User = Depends(require_perm("metric.import"))):
    content = build_metric_template(db)
    return _xlsx_response(content, "指标数据导入标准模板.xlsx")


@router.post("/import", response_model=ImportResult)
async def metric_import(
    request: Request,
    file: UploadFile = File(...),
    period: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("metric.import")),
):
    period = period or current_period()
    raw = await file.read()
    if len(raw) > settings.import_max_mb * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"文件不能超过 {settings.import_max_mb}MB")
    try:
        rows = parse_rows(raw, ["指标编码", "指标名称", "统计周期", "统计组织", "实际值"], settings.import_max_rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    valid, errors = validate_metric_rows(db, rows, period)
    if errors:
        return {"imported": 0, "errors": errors}
    count = import_metrics(db, valid, user)
    write_log(db, user, "import", "metric", "", {"count": count, "period": period}, request)
    db.commit()
    return {"imported": count, "errors": []}


def _xlsx_response(content: bytes, filename: str):
    from urllib.parse import quote

    from fastapi.responses import Response

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
