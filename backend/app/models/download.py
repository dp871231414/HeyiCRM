"""下载中心 · 导出记录模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DownloadRecord(Base):
    """下载中心导出记录。

    - 每次导出（任务清单 / 市场项目清单）先在下载中心生成一条记录、把文件落盘，再返回文件；
    - 文件按「对象标识 + 时间」自动命名（如 重点任务_20261017_091523.xlsx），记录只存文件名；
    - 列表仅展示创建人本人记录，文件下载 / 删除亦仅创建人本人可操作。
    """

    __tablename__ = "download_record"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    # 导出对象类型：task / market_project
    object_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 导出文件名称（自动按对象 + 时间命名）
    filename: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(16), ForeignKey("user.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
