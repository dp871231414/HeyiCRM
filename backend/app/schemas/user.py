"""角色与账号模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RoleOut(BaseModel):
    id: str
    name: str
    description: str = ""
    scope: str
    scopeLabel: str = ""
    isSystem: bool = False
    permissions: list[str] = []
    # 文档中心分组可见范围（两级权限第二级）；为空表示全部分组
    docGroups: list[str] = []
    userCount: int = 0


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = ""
    scope: str = "self"
    permissions: list[str] = []
    # 是否标记为内置角色（内置角色默认受删除保护，可由具备 account.role 权限者调整）
    isSystem: bool = False
    # 文档中心分组可见范围；为空表示全部分组
    docGroups: list[str] = []


class RoleUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = ""
    scope: str = "self"
    permissions: list[str] = []
    # 不传表示保持原值
    isSystem: bool | None = None
    # 不传表示保持原值
    docGroups: list[str] | None = None


class UserOut(BaseModel):
    id: str
    name: str
    account: str
    deptId: str
    deptName: str = ""
    roleId: str
    roleName: str = ""
    scope: str | None = None
    effectiveScope: str = ""
    status: str
    lastLoginAt: str | None = None
    lastLoginIp: str | None = None


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    account: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    dept_id: str
    role_id: str
    scope: str | None = None
    status: str = "active"


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    dept_id: str
    role_id: str
    scope: str | None = None
    status: str = "active"
    password: str | None = None


class StatusIn(BaseModel):
    status: str
