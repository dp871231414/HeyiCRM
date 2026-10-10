"""鉴权相关模型。"""
from __future__ import annotations

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


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBrief
    perms: list[str]


class MeOut(BaseModel):
    user: UserBrief
    perms: list[str]
    visibleOrgs: list[str] = []
