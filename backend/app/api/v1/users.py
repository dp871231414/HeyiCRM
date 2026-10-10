"""账号路由。"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import SCOPES
from app.core.deps import require_perm
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Organization, Role, User
from app.schemas.user import StatusIn, UserCreate, UserOut, UserUpdate
from app.services.audit import write_log
from app.services.serializers import user_out

router = APIRouter(prefix="/users", tags=["账号"])


def _next_user_id(db: Session) -> str:
    max_n = 0
    for uid in db.scalars(select(User.id)).all():
        m = re.fullmatch(r"U(\d+)", uid)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"U{max_n + 1:03d}"


def _validate_refs(db: Session, dept_id: str, role_id: str) -> None:
    if not db.get(Organization, dept_id):
        raise HTTPException(status_code=422, detail="所属部门不存在")
    if not db.get(Role, role_id):
        raise HTTPException(status_code=422, detail="角色不存在")


@router.get("", response_model=list[UserOut])
def list_users(
    keyword: str = "",
    dept_id: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.view")),
):
    q = select(User).order_by(User.id)
    if dept_id:
        q = q.where(User.dept_id == dept_id)
    if status:
        q = q.where(User.status == status)
    rows = db.scalars(q).all()
    if keyword:
        rows = [u for u in rows if keyword in u.name or keyword in u.account]
    return [user_out(db, u) for u in rows]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    account = payload.account.strip()
    if db.scalar(select(User).where(User.account == account)):
        raise HTTPException(status_code=409, detail="账号已存在，请更换账号名")
    _validate_refs(db, payload.dept_id, payload.role_id)
    scope = payload.scope if payload.scope in SCOPES else None
    uid = _next_user_id(db)
    new_user = User(
        id=uid,
        name=payload.name.strip(),
        account=account,
        password_hash=hash_password(payload.password),
        dept_id=payload.dept_id,
        role_id=payload.role_id,
        scope=scope,
        status=payload.status if payload.status in ("active", "disabled") else "active",
    )
    db.add(new_user)
    write_log(db, user, "create", "user", uid, {"account": account}, request)
    db.commit()
    db.refresh(new_user)
    return user_out(db, new_user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="账号不存在")
    _validate_refs(db, payload.dept_id, payload.role_id)
    target.name = payload.name.strip()
    target.dept_id = payload.dept_id
    target.role_id = payload.role_id
    # scope 传空串 → 删除覆盖值（跟随角色默认）
    target.scope = payload.scope if payload.scope in SCOPES else None
    target.status = payload.status if payload.status in ("active", "disabled") else target.status
    if payload.password:
        target.password_hash = hash_password(payload.password)
    write_log(db, user, "update", "user", user_id, {"name": target.name}, request)
    db.commit()
    db.refresh(target)
    return user_out(db, target)


@router.post("/{user_id}/status", response_model=UserOut)
def set_status(
    user_id: str,
    payload: StatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="账号不存在")
    if payload.status not in ("active", "disabled"):
        raise HTTPException(status_code=422, detail="状态取值非法")
    if target.id == user.id and payload.status == "disabled":
        raise HTTPException(status_code=409, detail="不能停用当前登录账号")
    target.status = payload.status
    write_log(db, user, "status", "user", user_id, {"status": payload.status}, request)
    db.commit()
    db.refresh(target)
    return user_out(db, target)
