"""鉴权相关模型。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    account: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserBrief(BaseModel):
    id: str
    name: str
    account: str
    deptId: str
    deptName: str
    roleId: str
    roleName: str
    scope: str
    status: str
    # 用户级偏好（行高、视图等），按账号记忆
    preferences: dict[str, Any] = {}


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBrief
    perms: list[str]


class MeOut(BaseModel):
    user: UserBrief
    perms: list[str]
    visibleOrgs: list[str] = []


class PrefsOut(BaseModel):
    preferences: dict[str, Any] = {}


class PrefsUpdate(BaseModel):
    # 仅接受合法键的偏好项，写入时与已有偏好做浅合并
    preferences: dict[str, Any] = {}
