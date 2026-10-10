"""指标相关模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MetricDefOut(BaseModel):
    id: str
    name: str
    unit: str = ""
    group: str
    family: str = ""
    parentId: str | None = None
    direction: str
    cycle: str
    weight: int = 0
    warn: float | None = None
    danger: float | None = None
    rateTarget: float | None = None
    snapshot: bool = False
    noTarget: bool = False
    ownerOrgId: str | None = None
    ownerOrgName: str = ""
    description: str = ""


class MetricValueIn(BaseModel):
    metric_id: str
    org_id: str
    period: str
    value: float | None = Field(default=None, description="传 null 表示清空该值")


class MetricRowOut(BaseModel):
    metricId: str
    name: str
    unit: str = ""
    group: str
    family: str = ""
    direction: str
    weight: int = 0
    snapshot: bool = False
    noTarget: bool = False
    ownerOrgId: str | None = None
    ownerOrgName: str = ""
    description: str = ""
    target: float | None = None
    actual: float | None = None
    rate: float | None = None
    rateText: str = "—"
    light: str = "none"
    gap: float | None = None
    hasCollection: bool = False
    collMetricId: str | None = None
    collActual: float | None = None
    collRate: float | None = None
    collLight: str = "none"
    vsTime: float | None = None
    periodLabel: str = ""


class BoardOut(BaseModel):
    period: str
    currentPeriod: str
    dataAsOf: str
    timeProgress: float
    orgId: str
    annual: list[MetricRowOut] = []
    monitor: list[MetricRowOut] = []
    project: dict = {}
    counts: dict = {}
