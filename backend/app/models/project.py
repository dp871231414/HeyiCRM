"""市场项目与漏斗配置模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketProject(Base):
    """市场项目 · 驾驶舱「市场项目概览」漏斗的数据来源。

    与「项目公司」（Organization.type=project）是两回事：
    项目公司是独立核算的组织单元；市场项目是销售线索/商机，按阶段推进。
    """

    __tablename__ = "market_project"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 需求车辆数（辆）：牵引车 / 挂车
    tractor_demand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trailer_demand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 项目阶段：10 / 25 / 50 / 75 / 90 / 100（见 constants.MARKET_STAGES）
    stage: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(16), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FunnelConfig(Base):
    """漏斗各阶段的转化概率 · 单行单阶段，缺省时按阶段百分比回落（见 services.funnel）。"""

    __tablename__ = "funnel_config"

    stage: Mapped[int] = mapped_column(Integer, primary_key=True)
    prob: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
