"""组织树常用查询 · 市场部子树、子部门列表等。

市场部（DEFAULT_MARKET_DEPT_ID）是经营驾驶舱「市场项目概览」筛选与
项目管理负责人范围的根节点，这里集中维护它的派生查询。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_MARKET_DEPT_ID
from app.models import Organization


def market_tree_ids(db: Session) -> set[str]:
    """市场部及其全部子孙部门的 ID 集合（含市场部自身）。"""
    rows = db.execute(select(Organization.id, Organization.parent_id)).all()
    children: dict[str | None, list[str]] = {}
    for oid, pid in rows:
        children.setdefault(pid, []).append(oid)

    ids: set[str] = set()
    stack = [DEFAULT_MARKET_DEPT_ID]
    while stack:
        cur = stack.pop()
        if cur in ids:
            continue
        ids.add(cur)
        for c in children.get(cur, []):
            stack.append(c)
    return ids


def market_sub_departments(db: Session) -> list[dict]:
    """市场部的直接子部门（二级部门）列表 · 用于漏斗筛选标签。

    只取直接子节点（不递归），排除项目公司；按 sort_order / id 排序。
    """
    rows = (
        db.execute(
            select(Organization)
            .where(
                Organization.parent_id == DEFAULT_MARKET_DEPT_ID,
                Organization.type != "project",
            )
            .order_by(Organization.sort_order, Organization.id)
        )
        .scalars()
        .all()
    )
    return [{"id": o.id, "name": o.name} for o in rows]
