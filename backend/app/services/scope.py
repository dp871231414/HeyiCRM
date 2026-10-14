"""可见范围服务 · 数据隔离的核心。

**适用范围（重要）**：数据可见范围**只作用于任务模块**（任务列表 / 详情 / 统计）。

    可见任务 = 任务所属组织 ∈ 可见组织  OR  责任人 = 本人姓名
用于解决「任务挂上级部门、责任人属下级」的归属问题。

经营驾驶舱与指标维护**不使用**本服务的过滤能力 —— 它们只按角色权限（菜单 / 操作权限）
判断能否查看与操作，数据一律按全公司口径返回。原因：全公司与项目公司不是递归汇总关系
（项目公司只承载运营收入，销售收入来自系统中的其他主体），按可见范围裁剪经营数据
会让人误读口径。相关说明见 `api/v1/dashboard.py`、`api/v1/metrics.py`。

规则：
- all       → 全部组织
- dept_sub  → 本部门及其所有子孙部门（递归）
- dept      → 仅本部门
- self      → 不按组织维度，只看指派给本人的数据（组织集合为空）
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
    """登录人的可见组织集合。

    当前供登录接口回传 `visibleOrgs` 使用（前端展示与任务模块的边界判断）。
    驾驶舱与指标维护不再用它过滤数据。
    """
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


def visible_market_project_filter(db: Session, user: User) -> ColumnElement[bool] | None:
    """市场项目的可见性条件 · 按「创建人归属部门」匹配数据范围（scope=all 返回 None）。

    与任务模块同一套逻辑，只是归属维度不同：任务看「责任部门 / 责任人」，
    项目没有部门字段，看「创建人所属部门 ∈ 可见组织」；本人创建的项目始终可见。
    """
    from app.models import MarketProject

    scope = effective_scope(db, user)
    if scope == "all":
        return None
    if scope == "self":
        return MarketProject.created_by == user.id
    orgs = visible_org_ids(db, user)
    if not orgs:
        return MarketProject.created_by == user.id
    creator_ids = select(User.id).where(User.dept_id.in_(orgs))
    return or_(MarketProject.created_by.in_(creator_ids), MarketProject.created_by == user.id)
