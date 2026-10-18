"""元数据路由 · 供任意已登录用户使用的基础字典（不含统计与敏感信息）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ORG_TYPE_PROJECT
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Organization, User
from app.services import scope as scope_svc
from app.services.org_tree import market_tree_ids

router = APIRouter(prefix="/meta", tags=["元数据"])


@router.get("/orgs")
def org_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """组织下拉选项：全公司 + 部门层级（不含项目公司）。"""
    rows = list(db.scalars(select(Organization).order_by(Organization.sort_order, Organization.id)).all())
    by_parent: dict[str | None, list[Organization]] = {}
    for o in rows:
        by_parent.setdefault(o.parent_id, []).append(o)

    out: list[dict] = []

    def walk(parent_id: str | None, depth: int) -> None:
        for o in by_parent.get(parent_id, []):
            if o.type == ORG_TYPE_PROJECT:
                continue
            out.append({"id": o.id, "name": o.name, "type": o.type, "parentId": o.parent_id, "head": o.head, "depth": depth})
            walk(o.id, depth + 1)

    walk(None, 0)
    return out


@router.get("/owners")
def owner_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """责任人候选：当前用户数据可见范围（scope）内的启用账号。

    scope=all → 全公司；dept_sub → 本部门及下属部门；dept → 本部门；self → 仅本人。
    与「新建任务 / 任务组」的责任人可选范围一致（见 services/scope.visible_user_filter）。
    返回 deptName（人员的直接所属部门名称，取自账号管理），供前端「责任人」下拉展示
    「姓名（部门）」并实时联动账号管理（部门调整后立即体现，无需手填）。
    """
    cond = scope_svc.visible_user_filter(db, user)
    q = select(User).where(User.status == "active")
    if cond is not None:
        q = q.where(cond)
    rows = db.scalars(q.order_by(User.id)).all()
    name_by_id = {o.id: o.name for o in db.scalars(select(Organization)).all()}
    return [
        {"id": u.id, "name": u.name, "deptId": u.dept_id, "deptName": name_by_id.get(u.dept_id, "")}
        for u in rows
    ]


@router.get("/market-owners")
def market_owner_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """项目管理（市场项目）负责人候选：仅市场部及其下属部门内的启用账号。

    返回每个人员的直接所属部门（deptId / deptName），供前端「选负责人后自动带出所属部门」。
    """
    market_ids = market_tree_ids(db)
    name_by_id = {o.id: o.name for o in db.scalars(select(Organization)).all()}
    rows = (
        db.execute(
            select(User)
            .where(User.status == "active", User.dept_id.in_(market_ids))
            .order_by(User.dept_id, User.id)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": u.id,
            "name": u.name,
            "deptId": u.dept_id,
            "deptName": name_by_id.get(u.dept_id, ""),
        }
        for u in rows
    ]
