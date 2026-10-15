"""市场项目相关模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MarketProjectOut(BaseModel):
    id: str
    name: str
    description: str = ""
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
