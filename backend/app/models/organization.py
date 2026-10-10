"""组织模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # company / dept / team / project
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("organization.id", ondelete="SET NULL"), nullable=True, index=True
    )
    head: Mapped[str] = mapped_column(String(32), default="—", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
