"""组织与项目公司模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class OrgOut(BaseModel):
    id: str
    name: str
    type: str
    parentId: str | None = None
    head: str = ""
    depth: int = 0
    userCount: int = 0
    childCount: int = 0
    taskCount: int = 0


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: str = "dept"
    parent_id: str = "CO"
    head: str = ""


class OrgUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    head: str = ""


class ImpactOut(BaseModel):
    users: int = 0
    children: int = 0
    tasks: int = 0
    targets: int = 0
    actuals: int = 0


class ProjectTargetIn(BaseModel):
    metric_id: str
    value: float
    year: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    head: str = ""
    targets: list[ProjectTargetIn] = []


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    head: str = ""
