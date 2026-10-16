"""市场项目相关模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MarketProjectOut(BaseModel):
    id: str
    name: str
    description: str = ""
    # 最新一条进展的冗余快照（= 最近一次写入的 ProjectProgress.content），列表「项目进展」列展示用
    latestProgress: str = ""
    tractorDemand: int = 0
    trailerDemand: int = 0
    stage: int
    stageLabel: str = ""
    owner: str
    ownerDeptId: str | None = None
    ownerDeptName: str = ""
    # 系统自动记录，只读（不接受前端写入）
    createdById: str = ""
    createdByName: str = ""
    createdAt: str = ""
    updatedAt: str = ""


class MarketProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="项目名称")
    description: str = ""
    # 项目进展：创建时必填，作为该项目的第一条进展记录（时间轴展示）
    progress: str = Field(min_length=1, max_length=2000, description="项目进展（必填，写入第一条进展记录）")
    tractor_demand: int = Field(default=0, ge=0, description="牵引车需求数（辆）")
    trailer_demand: int = Field(default=0, ge=0, description="挂车需求数（辆）")
    stage: int = Field(description="项目阶段：10/25/50/75/90/100")
    owner: str = Field(min_length=1, max_length=32, description="负责人")
    owner_dept_id: str | None = Field(default=None, description="负责人直接所属部门（选负责人后自动带出）")


class MarketProjectUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    tractor_demand: int = Field(default=0, ge=0)
    trailer_demand: int = Field(default=0, ge=0)
    stage: int
    owner: str = Field(min_length=1, max_length=32)
    # 编辑界面不再直接改进展（只能通过「新增进展」追加记录），后端忽略该字段
    owner_dept_id: str | None = Field(default=None, description="负责人直接所属部门（选负责人后自动带出）")


class MarketProjectListOut(BaseModel):
    items: list[MarketProjectOut]
    total: int
    page: int
    size: int


class FunnelProbItem(BaseModel):
    stage: int
    prob: float = Field(ge=0, le=1, description="转化概率 0~1")


class FunnelConfigIn(BaseModel):
    probs: list[FunnelProbItem] = Field(min_length=1, description="六个阶段的转化概率（整份保存）")


class ProjectProgressItem(BaseModel):
    id: int
    content: str
    createdById: str = ""
    createdByName: str = ""
    createdAt: str = ""


class ProjectProgressListOut(BaseModel):
    items: list[ProjectProgressItem]
    total: int
    page: int
    size: int


class ProjectProgressCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000, description="本次项目进展内容")
