"""角色与权限元数据路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ALL_PERM_KEYS, PERM_GROUPS, SCOPES
from app.core.deps import require_perm
from app.db.session import get_db
from app.models import Role, User
from app.schemas.user import RoleCreate, RoleOut, RoleUpdate
from app.services.audit import write_log
from app.services.serializers import role_out

router = APIRouter(tags=["角色与权限"])


@router.get("/permissions")
def permissions(user: User = Depends(require_perm("account.view"))):
    """权限清单与可见范围选项，供角色编辑界面渲染。"""
    return {
        "groups": PERM_GROUPS,
        "scopes": [{"value": k, "label": v} for k, v in SCOPES.items()],
    }


@router.get("/roles", response_model=list[RoleOut])
def list_roles(keyword: str = "", db: Session = Depends(get_db), user: User = Depends(require_perm("account.view"))):
    roles = db.scalars(select(Role).order_by(Role.is_system.desc(), Role.id)).all()
    if keyword:
        roles = [r for r in roles if keyword in r.name]
    return [role_out(db, r) for r in roles]


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(
    payload: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.role")),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="角色名称不能为空")
    if db.scalar(select(Role).where(Role.name == name)):
        raise HTTPException(status_code=409, detail="已存在同名角色，请更换名称")
    perms = [p for p in payload.permissions if p in ALL_PERM_KEYS]
    role = Role(
        id=f"role_{int(__import__('time').time() * 1000):x}",
        name=name,
        description=payload.description.strip(),
        scope=payload.scope if payload.scope in SCOPES else "self",
        is_system=False,
        permissions=perms,
    )
    db.add(role)
    write_log(db, user, "create", "role", role.id, {"name": name, "perms": perms}, request)
    db.commit()
    db.refresh(role)
    return role_out(db, role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: str,
    payload: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.role")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="角色名称不能为空")
    dup = db.scalar(select(Role).where(Role.name == name, Role.id != role_id))
    if dup:
        raise HTTPException(status_code=409, detail="已存在同名角色，请更换名称")
    role.name = name
    role.description = payload.description.strip()
    role.scope = payload.scope if payload.scope in SCOPES else role.scope
    role.permissions = [p for p in payload.permissions if p in ALL_PERM_KEYS]
    write_log(db, user, "update", "role", role_id, {"name": name}, request)
    db.commit()
    db.refresh(role)
    return role_out(db, role)


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.role")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=409, detail="内置角色不可删除")
    n = len(db.scalars(select(User.id).where(User.role_id == role_id)).all())
    if n > 0:
        raise HTTPException(status_code=409, detail=f"该角色下仍有 {n} 个账号，请先调整这些账号的角色")
    db.delete(role)
    write_log(db, user, "delete", "role", role_id, {"name": role.name}, request)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": role_id}}
