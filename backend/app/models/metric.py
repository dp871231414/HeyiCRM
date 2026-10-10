"""指标模型：定义 / 目标值 / 实际值。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MetricDef(Base):
    __tablename__ = "metric_def"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    # annual / project / monitor
    group: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # revenue / collection / digest / op / incident / fault / rent
    family: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("metric_def.id"), nullable=True)
    # positive / negative
    direction: Mapped[str] = mapped_column(String(8), default="positive", nullable=False)
    # month / quarter / year
    cycle: Mapped[str] = mapped_column(String(8), default="month", nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warn: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    danger: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    rate_target: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    is_snapshot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    no_target: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_org_id: Mapped[str | None] = mapped_column(String(16), ForeignKey("organization.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MetricTarget(Base):
    __tablename__ = "metric_target"
    __table_args__ = (UniqueConstraint("metric_id", "org_id", "period", name="uq_target"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[str] = mapped_column(String(32), ForeignKey("metric_def.id"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(16), ForeignKey("organization.id"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MetricActual(Base):
    __tablename__ = "metric_actual"
    __table_args__ = (UniqueConstraint("metric_id", "org_id", "period", name="uq_actual"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[str] = mapped_column(String(32), ForeignKey("metric_def.id"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(16), ForeignKey("organization.id"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(16), ForeignKey("user.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
