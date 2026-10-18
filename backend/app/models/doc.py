"""文档中心 · 数据库存储模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemDoc(Base):
    """系统文档（使用说明 / 产品需求 / 技术 / 测试 / 设计 / Skill / 项目开发说明）。

    内容存库，供「系统配置 → 使用说明」菜单读取渲染；每次迭代由 /sync 刷新。
    """

    __tablename__ = "system_doc"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    doc_key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    fmt: Mapped[str] = mapped_column(String(16), default="markdown", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
