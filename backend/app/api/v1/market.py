"""市场项目路由：项目（商机）的增删改查。

**权限口径**：与任务模块一致 —— 列表 / 详情 / 编辑按**数据可见范围（scope）**隔离，
归属维度是「创建人所属部门」（项目本身没有部门字段）；
经营驾驶舱的漏斗统计不走这里，只按角色权限开放（见 `api/v1/dashboard.py`）。

注意与 `/projects`（项目公司，独立核算组织）区分：本模块是销售商机项目。
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.constants import MARKET_PROJECT_ID_PREFIX, MARKET_STAGE_VALUES, MARKET_STAGES
from app.core.deps import require_perm
from app.db.session import get_db
from app.models import MarketProject, User
from app.schemas.project import (
    MarketProjectCreate,
    MarketProjectListOut,
    MarketProjectOut,
    MarketProjectUpdate,
)
from app.services import scope as scope_svc
from app.services.audit import write_log

router = APIRouter(prefix="/market-projects", tags=["项目管理"])

_STAGE_LABELS = {s["stage"]: s["label"] for s in MARKET_STAGES}

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


def next_project_id(db: Session) -> str:
    """MP0001 递增（不复用已删除的号段）。"""
    max_seq = 0
    for pid in db.scalars(select(MarketProject.id)).all():
        m = re.fullmatch(rf"{MARKET_PROJECT_ID_PREFIX}(\d+)", pid)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"{MARKET_PROJECT_ID_PREFIX}{max_seq + 1:04d}"


def _to_dict(db: Session, p: MarketProject, creator_names: dict[str, str] | None = None) -> dict:
    if creator_names is None:
        creator_names = {}
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "tractorDemand": int(p.tractor_demand or 0),
        "trailerDemand": int(p.trailer_demand or 0),
        "stage": int(p.stage),
        "stageLabel": _STAGE_LABELS.get(int(p.stage), ""),
        "owner": p.owner,
        "createdById": p.created_by or "",
        "createdByName": creator_names.get(p.created_by or "", ""),
        "createdAt": p.created_at.isoformat() if p.created_at else "",
        "updatedAt": p.updated_at.isoformat() if p.updated_at else "",
    }


def _enrich_creators(db: Session, items: list[dict]) -> list[dict]:
    """批量补齐创建人姓名（去重一次查，避免 N+1）。"""
    ids = {it["createdById"] for it in items if it["createdById"]}
    names = {}
    if ids:
        names = {uid: name for uid, name in db.execute(select(User.id, User.name).where(User.id.in_(ids))).all()}
    for it in items:
        it["createdByName"] = names.get(it["createdById"], "")
    return items


def _visible_query(db: Session, user: User):
    q = select(MarketProject)
    cond = scope_svc.visible_market_project_filter(db, user)
    if cond is not None:
        q = q.where(cond)
    return q


def _project_or_404(db: Session, user: User, project_id: str) -> MarketProject:
    p = db.get(MarketProject, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    cond = scope_svc.visible_market_project_filter(db, user)
    if cond is not None:
        visible = db.scalar(select(MarketProject).where(MarketProject.id == project_id, cond))
        if not visible:
            raise HTTPException(status_code=403, detail="无权访问该项目")
    return p


def _apply_payload(p: MarketProject, payload) -> None:
    if payload.stage not in MARKET_STAGE_VALUES:
        raise HTTPException(status_code=422, detail="项目阶段不合法")
    p.name = payload.name.strip()
    if not p.name:
        raise HTTPException(status_code=422, detail="项目名称不能为空")
    p.description = payload.description or ""
    p.tractor_demand = int(payload.tractor_demand or 0)
    p.trailer_demand = int(payload.trailer_demand or 0)
    p.stage = int(payload.stage)
    p.owner = payload.owner.strip()


@router.get("", response_model=MarketProjectListOut)
def list_projects(
    keyword: str = "",
    stage: int | None = None,
    page: int = 1,
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.view")),
):
    page = max(1, page)
    q = _visible_query(db, user)
    if stage is not None:
        q = q.where(MarketProject.stage == stage)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(MarketProject.name.like(like), MarketProject.owner.like(like), MarketProject.id.like(like)))

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = list(db.scalars(q.order_by(MarketProject.id).limit(size).offset((page - 1) * size)).all())
    return {
        "items": _enrich_creators(db, [_to_dict(db, p) for p in rows]),
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/{project_id}", response_model=MarketProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(require_perm("market.view"))):
    p = _project_or_404(db, user, project_id)
    return _enrich_creators(db, [_to_dict(db, p)])[0]


@router.post("", response_model=MarketProjectOut, status_code=201)
def create_project(
    payload: MarketProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.edit")),
):
    pid = next_project_id(db)
    p = MarketProject(id=pid, created_by=user.id)
    _apply_payload(p, payload)
    db.add(p)
    write_log(db, user, "create", "market_project", pid, {"name": p.name}, request)
    db.commit()
    db.refresh(p)
    return _enrich_creators(db, [_to_dict(db, p)])[0]


@router.patch("/{project_id}", response_model=MarketProjectOut)
def update_project(
    project_id: str,
    payload: MarketProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.edit")),
):
    p = _project_or_404(db, user, project_id)
    _apply_payload(p, payload)
    write_log(db, user, "update", "market_project", project_id, {"name": p.name}, request)
    db.commit()
    db.refresh(p)
    return _enrich_creators(db, [_to_dict(db, p)])[0]


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.delete")),
):
    p = _project_or_404(db, user, project_id)
    db.delete(p)
    write_log(db, user, "delete", "market_project", project_id, {"name": p.name}, request)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": project_id}}
