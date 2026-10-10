"""任务与操作日志模型。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Task(Base):
    __tablename__ = "task"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    abnormal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    target: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    done: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    dept_id: Mapped[str] = mapped_column(String(16), ForeignKey("organization.id"), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(16), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OperationLog(Base):
    __tablename__ = "operation_log"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[str | None] = mapped_column(String(16), ForeignKey("user.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
