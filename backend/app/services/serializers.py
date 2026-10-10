"""ORM → 前端字典的序列化辅助。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import SCOPES
from app.core.deps import effective_scope
from app.models import MetricActual, MetricTarget, Organization, Role, Task, User


def org_name(db: Session, org_id: str | None) -> str:
    if not org_id:
        return "—"
    org = db.get(Organization, org_id)
    return org.name if org else "—"


def user_brief(db: Session, user: User) -> dict:
    role = db.get(Role, user.role_id)
    return {
        "id": user.id,
        "name": user.name,
        "account": user.account,
        "deptId": user.dept_id,
        "deptName": org_name(db, user.dept_id),
        "roleId": user.role_id,
        "roleName": role.name if role else "",
        "scope": effective_scope(db, user),
        "status": user.status,
    }


def role_out(db: Session, role: Role, user_count: int | None = None) -> dict:
    if user_count is None:
        user_count = db.scalar(select(func.count()).select_from(User).where(User.role_id == role.id)) or 0
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "scope": role.scope,
        "scopeLabel": SCOPES.get(role.scope, role.scope),
        "isSystem": bool(role.is_system),
        "permissions": list(role.permissions or []),
        "userCount": int(user_count),
    }


def user_out(db: Session, user: User) -> dict:
    role = db.get(Role, user.role_id)
    return {
        "id": user.id,
        "name": user.name,
        "account": user.account,
        "deptId": user.dept_id,
        "deptName": org_name(db, user.dept_id),
        "roleId": user.role_id,
        "roleName": role.name if role else "",
        "scope": user.scope,
        "effectiveScope": effective_scope(db, user),
        "status": user.status,
        "lastLoginAt": user.last_login_at.strftime("%Y-%m-%d %H:%M") if user.last_login_at else None,
        "lastLoginIp": user.last_login_ip,
    }


def org_counts(db: Session) -> dict[str, dict]:
    users = dict(db.execute(select(User.dept_id, func.count()).group_by(User.dept_id)).all())
    children = dict(db.execute(select(Organization.parent_id, func.count()).group_by(Organization.parent_id)).all())
    tasks = dict(db.execute(select(Task.dept_id, func.count()).group_by(Task.dept_id)).all())
    return {
        "users": {k: int(v) for k, v in users.items()},
        "children": {k: int(v) for k, v in children.items() if k},
        "tasks": {k: int(v) for k, v in tasks.items()},
    }


def project_impact(db: Session, org_id: str) -> dict:
    return {
        "targets": db.scalar(select(func.count()).select_from(MetricTarget).where(MetricTarget.org_id == org_id)) or 0,
        "actuals": db.scalar(select(func.count()).select_from(MetricActual).where(MetricActual.org_id == org_id)) or 0,
        "tasks": db.scalar(select(func.count()).select_from(Task).where(Task.dept_id == org_id)) or 0,
        "users": db.scalar(select(func.count()).select_from(User).where(User.dept_id == org_id)) or 0,
    }
