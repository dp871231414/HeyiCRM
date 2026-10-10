"""FastAPI 依赖：当前用户、权限校验、可见范围。"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import Role, User

COOKIE_NAME = "access_token"


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")

    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")
    return user


def get_user_perms(db: Session, user: User) -> list[str]:
    role = db.get(Role, user.role_id)
    return list(role.permissions or []) if role else []


def require_perm(perm: str):
    """依赖工厂：要求拥有指定权限，否则 403。"""

    def _dep(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if perm not in get_user_perms(db, user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无此操作权限")
        return user

    return _dep


def require_any_perm(perms: list[str]):
    """依赖工厂：拥有任一权限即可。"""

    def _dep(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        user_perms = get_user_perms(db, user)
        if not any(p in user_perms for p in perms):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无此操作权限")
        return user

    return _dep


def user_has_perm(db: Session, user: User, perm: str) -> bool:
    return perm in get_user_perms(db, user)


def get_role(db: Session, user: User) -> Role | None:
    return db.get(Role, user.role_id)


def role_scope(db: Session, user: User) -> str:
    role = get_role(db, user)
    return role.scope if role else "self"


def effective_scope(db: Session, user: User) -> str:
    """账号 scope 覆盖角色默认范围。"""
    return user.scope or role_scope(db, user)


def all_org_ids(db: Session) -> list[str]:
    from app.models import Organization

    return list(db.scalars(select(Organization.id)).all())
