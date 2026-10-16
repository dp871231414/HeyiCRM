"""鉴权路由：登录 / 登出 / 当前用户。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import COOKIE_NAME, get_current_user, get_user_perms
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginIn, LoginOut, MeOut, PrefsOut, PrefsUpdate
from app.services import scope as scope_svc
from app.services.audit import write_log
from app.services.serializers import user_brief

router = APIRouter(prefix="/auth", tags=["鉴权"])

# 偏好允许的键与取值（前端写入时只接受这些，避免脏数据）
ALLOWED_PREF_KEYS = {"rowHeight"}
ROW_HEIGHT_VALUES = {"default", "high", "ultra"}


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.account == payload.account))
    # 统一文案，不泄露账号是否存在
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")

    token = create_access_token(user.id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )

    from app.core.deps import get_client_ip

    user.last_login_at = datetime.now()
    user.last_login_ip = get_client_ip(request)
    write_log(db, user, "login", "user", user.id, request=request)
    db.commit()
    db.refresh(user)

    return {"access_token": token, "token_type": "bearer", "user": user_brief(db, user), "perms": get_user_perms(db, user)}


@router.post("/logout")
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    write_log(db, user, "logout", "user", user.id)
    db.commit()
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True, "msg": "已登出"}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "user": user_brief(db, user),
        "perms": get_user_perms(db, user),
        # 可见组织集合 · 供任务模块的边界判断使用；驾驶舱与指标维护不按数据范围过滤
        "visibleOrgs": scope_svc.visible_org_ids(db, user),
    }


@router.get("/preferences", response_model=PrefsOut)
def get_preferences(user: User = Depends(get_current_user)):
    """读取当前账号的偏好设置（行高、视图等），随账号记忆。"""
    return {"preferences": dict(user.preferences or {})}


@router.put("/preferences", response_model=PrefsOut)
def update_preferences(payload: PrefsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新当前账号的偏好设置（浅合并），按账号记忆、下次登录仍生效。"""
    current = dict(user.preferences or {})
    for key, value in (payload.preferences or {}).items():
        if key not in ALLOWED_PREF_KEYS:
            continue
        # 行高取值做白名单校验
        if key == "rowHeight" and value not in ROW_HEIGHT_VALUES:
            continue
        current[key] = value
    user.preferences = current
    db.commit()
    db.refresh(user)
    return {"preferences": current}
