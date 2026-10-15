"""组织路由：组织树、部门增改删、影响面。"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import (
    DEFAULT_MARKET_DEPT_ID,
    ORG_TYPE_COMPANY,
    ORG_TYPE_DEPT,
    ORG_TYPE_PROJECT,
    ORG_TYPE_TEAM,
)
from app.core.deps import require_perm
from app.db.session import get_db
from app.models import MetricActual, MetricTarget, Organization, Task, User
from app.schemas.org import ImpactOut, OrgCreate, OrgOut, OrgUpdate
from app.services.audit import write_log
from app.services.serializers import org_counts

router = APIRouter(prefix="/orgs", tags=["组织"])


def _next_dept_id(db: Session) -> str:
    ids = db.scalars(select(Organization.id).where(Organization.id.like("D%"))).all()
    max_n = 0
    for oid in ids:
        m = re.fullmatch(r"D(\d+)", oid)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"D{max_n + 1:02d}"


def _org_payload(db: Session, org: Organization, depth: int | None = None) -> dict:
    """单个组织节点的完整信息（含真实 depth 与统计数）。

    创建 / 更新接口原先返回硬编码的 depth 与统计值（update 恒为 depth=0、各项计数为 0），
    前端若拿它就地更新列表，缩进层级和统计数字都会出错。这里统一给出真实值，
    前端保存后即可直接替换本地节点，无需重拉整棵组织树。
    """
    if depth is None:
        depth = 0
        cursor = org
        while cursor.parent_id:
            parent = db.get(Organization, cursor.parent_id)
            if not parent:
                break
            depth += 1
            cursor = parent
    counts = org_counts(db)
    return {
        "id": org.id,
        "name": org.name,
        "type": org.type,
        "parentId": org.parent_id,
        "head": org.head,
        "depth": depth,
        "userCount": counts["users"].get(org.id, 0),
        "childCount": counts["children"].get(org.id, 0),
        "taskCount": counts["tasks"].get(org.id, 0),
    }


def _build_tree(db: Session, include_project: bool = False) -> list[dict]:
    rows = list(db.scalars(select(Organization).order_by(Organization.sort_order, Organization.id)).all())
    counts = org_counts(db)
    by_parent: dict[str | None, list[Organization]] = {}
    for o in rows:
        by_parent.setdefault(o.parent_id, []).append(o)

    out: list[dict] = []

    def walk(parent_id: str | None, depth: int) -> None:
        for o in by_parent.get(parent_id, []):
            if not include_project and o.type == ORG_TYPE_PROJECT:
                continue
            out.append(
                {
                    "id": o.id,
                    "name": o.name,
                    "type": o.type,
                    "parentId": o.parent_id,
                    "head": o.head,
                    "depth": depth,
                    "userCount": counts["users"].get(o.id, 0),
                    "childCount": counts["children"].get(o.id, 0),
                    "taskCount": counts["tasks"].get(o.id, 0),
                }
            )
            walk(o.id, depth + 1)

    walk(None, 0)
    return out


def _impact(db: Session, org_id: str) -> dict:
    return {
        "users": db.scalar(select(func.count()).select_from(User).where(User.dept_id == org_id)) or 0,
        "children": db.scalar(
            select(func.count()).select_from(Organization).where(
                Organization.parent_id == org_id, Organization.type != ORG_TYPE_PROJECT
            )
        )
        or 0,
        "tasks": db.scalar(select(func.count()).select_from(Task).where(Task.dept_id == org_id)) or 0,
        "targets": db.scalar(select(func.count()).select_from(MetricTarget).where(MetricTarget.org_id == org_id)) or 0,
        "actuals": db.scalar(select(func.count()).select_from(MetricActual).where(MetricActual.org_id == org_id)) or 0,
    }


@router.get("", response_model=list[OrgOut])
def list_orgs(flat: int = 1, db: Session = Depends(get_db), user: User = Depends(require_perm("account.view"))):
    if flat:
        return _build_tree(db, include_project=False)
    # 树形结构
    flat_list = _build_tree(db, include_project=False)
    nodes = {o["id"]: {**o, "children": []} for o in flat_list}
    roots: list[dict] = []
    for o in flat_list:
        node = nodes[o["id"]]
        if o["parentId"] and o["parentId"] in nodes:
            nodes[o["parentId"]]["children"].append(node)
        else:
            roots.append(node)
    return roots


@router.post("", response_model=OrgOut, status_code=201)
def create_org(
    payload: OrgCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="部门名称不能为空")
    if db.scalar(select(Organization).where(Organization.name == name)):
        raise HTTPException(status_code=409, detail="已存在同名部门，请更换名称")
    parent = payload.parent_id or "CO"
    parent_org = db.get(Organization, parent)
    if not parent_org:
        raise HTTPException(status_code=422, detail="上级组织不存在")

    oid = _next_dept_id(db)
    org = Organization(
        id=oid,
        name=name,
        type=ORG_TYPE_DEPT if parent == "CO" else ORG_TYPE_TEAM,
        parent_id=parent,
        head=(payload.head or "").strip() or "—",
    )
    db.add(org)
    write_log(db, user, "create", "org", oid, {"name": name, "parent": parent}, request)
    db.commit()
    db.refresh(org)
    return _org_payload(db, org)


@router.patch("/{org_id}", response_model=OrgOut)
def update_org(
    org_id: str,
    payload: OrgUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    # 公司节点（全公司）同样允许编辑名称与负责人；删除仍受限（见 delete_org）
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="部门名称不能为空")
    dup = db.scalar(select(Organization).where(Organization.name == name, Organization.id != org_id))
    if dup:
        raise HTTPException(status_code=409, detail="已存在同名部门，请更换名称")
    org.name = name
    org.head = (payload.head or "").strip() or "—"
    write_log(db, user, "update", "org", org_id, {"name": name}, request)
    db.commit()
    db.refresh(org)
    return _org_payload(db, org)


@router.get("/{org_id}/impact", response_model=ImpactOut)
def org_impact(org_id: str, db: Session = Depends(get_db), user: User = Depends(require_perm("account.view"))):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    return _impact(db, org_id)


@router.delete("/{org_id}")
def delete_org(
    org_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    # 系统默认市场部：按 ID 锁定，不可删除（名称与负责人仍可修改）
    if org.id == DEFAULT_MARKET_DEPT_ID:
        raise HTTPException(status_code=409, detail="市场部为系统默认部门，不可删除，仅可修改名称与负责人")
    if org.type == ORG_TYPE_COMPANY:
        raise HTTPException(status_code=409, detail="全公司为根节点，不可删除")
    if org.type == ORG_TYPE_PROJECT:
        raise HTTPException(status_code=409, detail="项目公司请到指标维护页维护")

    imp = _impact(db, org_id)
    if imp["users"] > 0:
        raise HTTPException(status_code=409, detail=f"该部门下有 {imp['users']} 个账号，不允许删除，仅可修改")
    if imp["children"] > 0:
        raise HTTPException(status_code=409, detail=f"该部门下有 {imp['children']} 个下级部门，请先删除下级部门")

    parent = org.parent_id or "CO"
    # 任务上移到上级部门，避免无归属数据
    for task in db.scalars(select(Task).where(Task.dept_id == org_id)).all():
        task.dept_id = parent
    db.delete(org)
    write_log(db, user, "delete", "org", org_id, {"name": org.name, "tasksMoved": imp["tasks"]}, request)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": org_id, "impact": imp}}
