"""项目公司路由：独立核算单元的增删改查。"""
from __future__ import annotations

import re
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ORG_TYPE_PROJECT
from app.core.deps import require_perm
from app.db.session import get_db
from app.models import MetricActual, MetricTarget, Organization, Task, User
from app.schemas.org import ImpactOut, ProjectCreate, ProjectUpdate
from app.services.audit import write_log
from app.services.serializers import project_impact

router = APIRouter(prefix="/projects", tags=["项目公司"])


def _next_project_id(db: Session) -> str:
    max_n = 0
    for oid in db.scalars(select(Organization.id)).all():
        m = re.fullmatch(r"PC(\d+)", oid)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"PC{max_n + 1}"


def _project_out(db: Session, org: Organization) -> dict:
    imp = project_impact(db, org.id)
    return {
        "id": org.id,
        "name": org.name,
        "head": org.head,
        "parentId": org.parent_id,
        "impact": imp,
    }


@router.get("")
def list_projects(db: Session = Depends(get_db), user: User = Depends(require_perm("metric.view"))):
    from app.services import scope as scope_svc

    visible = scope_svc.visible_org_ids(db, user)
    orgs = db.scalars(
        select(Organization).where(Organization.type == ORG_TYPE_PROJECT).order_by(Organization.id)
    ).all()
    return [
        {"id": o.id, "name": o.name, "head": o.head, "parentId": o.parent_id, "impact": project_impact(db, o.id)}
        for o in orgs
        if o.id in visible
    ]


@router.post("", status_code=201)
def create_project(
    payload: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("metric.edit")),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="公司名称不能为空")
    if db.scalar(select(Organization).where(Organization.name == name)):
        raise HTTPException(status_code=409, detail="已存在同名组织，请更换名称")

    oid = _next_project_id(db)
    org = Organization(id=oid, name=name, type=ORG_TYPE_PROJECT, parent_id="CO", head=(payload.head or "").strip() or "—")
    db.add(org)

    for t in payload.targets:
        value = float(t.value)
        if value < 0:
            continue
        db.add(MetricTarget(metric_id=t.metric_id, org_id=oid, period=str(t.year), value=Decimal(str(value))))

    write_log(db, user, "create", "project", oid, {"name": name}, request)
    db.commit()
    return {"ok": True, "msg": "已新增项目公司", "data": {"id": oid, "name": name}}


@router.patch("/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("metric.edit")),
):
    org = db.get(Organization, project_id)
    if not org or org.type != ORG_TYPE_PROJECT:
        raise HTTPException(status_code=404, detail="仅可编辑项目公司")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="公司名称不能为空")
    dup = db.scalar(select(Organization).where(Organization.name == name, Organization.id != project_id))
    if dup:
        raise HTTPException(status_code=409, detail="已存在同名组织，请更换名称")
    org.name = name
    org.head = (payload.head or "").strip() or "—"
    write_log(db, user, "update", "project", project_id, {"name": name}, request)
    db.commit()
    return {"ok": True, "msg": "已保存", "data": {"id": project_id, "name": name}}


@router.get("/{project_id}/impact", response_model=ImpactOut)
def impact(project_id: str, db: Session = Depends(get_db), user: User = Depends(require_perm("metric.view"))):
    org = db.get(Organization, project_id)
    if not org or org.type != ORG_TYPE_PROJECT:
        raise HTTPException(status_code=404, detail="仅可查看项目公司")
    return project_impact(db, project_id)


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("metric.edit")),
):
    org = db.get(Organization, project_id)
    if not org or org.type != ORG_TYPE_PROJECT:
        raise HTTPException(status_code=404, detail="仅可删除项目公司")
    imp = project_impact(db, project_id)

    for row in db.scalars(select(MetricTarget).where(MetricTarget.org_id == project_id)).all():
        db.delete(row)
    for row in db.scalars(select(MetricActual).where(MetricActual.org_id == project_id)).all():
        db.delete(row)
    for t in db.scalars(select(Task).where(Task.dept_id == project_id)).all():
        db.delete(t)
    # 关联账号不删除，改为停用，保留历史痕迹
    for u in db.scalars(select(User).where(User.dept_id == project_id)).all():
        u.status = "disabled"
    db.delete(org)

    write_log(db, user, "delete", "project", project_id, {"name": org.name, "impact": imp}, request)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": project_id, "name": org.name, "impact": imp}}
