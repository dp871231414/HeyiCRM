"""账号与角色模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(Base):
    __tablename__ = "role"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # self / dept / dept_sub / all
    scope: Mapped[str] = mapped_column(String(16), default="self", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 权限 key 数组，如 ["dashboard.view", "task.view", ...]
    permissions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # 文档中心分组可见范围（两级权限的第二级）：允许查看的文档分组列表；
    # 为空表示「全部分组」（如管理员）。与 doc.view 菜单权限配合使用。
    doc_groups: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    account: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    dept_id: Mapped[str] = mapped_column(String(16), ForeignKey("organization.id"), nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(String(32), ForeignKey("role.id"), nullable=False, index=True)
    # 覆盖角色默认可见范围；为空则跟随角色
    scope: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # active / disabled
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    # 用户级偏好（JSON）：如行高 rowHeight=default|high|ultra，按账号记忆、下次登录仍生效
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
