"""可见范围服务 · 数据隔离的核心。

规则：
- all       → 全部组织
- dept_sub  → 本部门及其所有子孙部门（递归）
- dept      → 仅本部门
- self      → 不按组织维度，只看指派给本人的数据（组织集合为空）

任务可见性额外有一条兜底规则：
    可见任务 = 任务所属组织 ∈ 可见组织  OR  责任人 = 本人姓名
用于解决「任务挂上级部门、责任人属下级」的归属问题。
"""
from __future__ import annotations

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.orm import Session

from app.core.deps import effective_scope
from app.models import Organization, Task, User


def _children_map(db: Session) -> dict[str | None, list[str]]:
    rows = db.execute(select(Organization.id, Organization.parent_id)).all()
    out: dict[str | None, list[str]] = {}
    for oid, pid in rows:
        out.setdefault(pid, []).append(oid)
    return out


def visible_org_ids(db: Session, user: User) -> list[str]:
    scope = effective_scope(db, user)
    if scope == "all":
        return list(db.scalars(select(Organization.id)).all())
    if scope == "self":
        return []
    if scope == "dept_sub":
        children = _children_map(db)
        out: list[str] = [user.dept_id]
        stack = [user.dept_id]
        while stack:
            cur = stack.pop()
            for child in children.get(cur, []):
                if child not in out:
                    out.append(child)
                    stack.append(child)
        return out
    return [user.dept_id]


def org_in_scope(db: Session, user: User, org_id: str) -> bool:
    return org_id in visible_org_ids(db, user)


def visible_task_filter(db: Session, user: User) -> ColumnElement[bool] | None:
    """返回任务可见性的 SQL 条件；scope=all 时返回 None 表示不过滤。"""
    scope = effective_scope(db, user)
    if scope == "all":
        return None
    if scope == "self":
        return Task.owner == user.name
    orgs = visible_org_ids(db, user)
    if not orgs:
        return Task.owner == user.name
    return or_(Task.dept_id.in_(orgs), Task.owner == user.name)
