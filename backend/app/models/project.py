"""市场项目与漏斗配置模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    # 最新一条进展的冗余快照（= 最近一次写入的 ProjectProgress.content），供列表列 / 导出展示，避免每行子查询。
    # 编辑项目时不可直接改此处，只能「新增进展」追加记录，由后端同步为最新一条。
    progress: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 需求车辆数（辆）：牵引车 / 挂车
    tractor_demand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trailer_demand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 项目阶段：10 / 25 / 50 / 75 / 90 / 100（见 constants.MARKET_STAGES）
    stage: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(32), nullable=False)
    # 负责人直接所属部门（选负责人后自动带出并落库，用于漏斗按二级部门筛选）
    owner_dept_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("organization.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(String(16), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProjectTractorRequirement(Base):
    """项目车头需求明细 · 子列表。

    - 一条项目可有多个车头需求行（车辆型号 / 电池度数 / 数量）；
    - 列表「车头数量」= 各明细行数量汇总，冗余存于 market_project.tractor_demand（供驾驶舱漏斗复用）；
    - 删除项目时一并级联删除。
    """

    __tablename__ = "project_tractor_requirement"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("market_project.id"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(64), default="", nullable=False)  # 车辆型号（取自数据字典）
    battery: Mapped[str] = mapped_column(String(32), default="", nullable=False)  # 电池度数
    qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 数量（辆）


class ProjectTrailerRequirement(Base):
    """项目挂车需求明细 · 子列表（结构同车头需求）。"""

    __tablename__ = "project_trailer_requirement"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("market_project.id"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(64), default="", nullable=False)  # 挂车型号（取自数据字典）
    battery: Mapped[str] = mapped_column(String(32), default="", nullable=False)  # 电池度数
    qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 数量（辆）


class ProjectProgress(Base):
    """项目进展记录 · 时间轴（参考 TaskProgress）。

    - 新增项目时若填了项目进展，写入第一条记录；
    - 编辑界面不可直接改进展，只能通过「新增进展」追加记录（每条独立保留）；
    - market_project.progress 为冗余的「最新进展」快照，供列表列/导出展示，避免每行子查询。
    """

    __tablename__ = "project_progress"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    project_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("market_project.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(16), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class FunnelConfig(Base):
    """漏斗各阶段的转化概率 · 单行单阶段，缺省时按阶段百分比回落（见 services.funnel）。"""

    __tablename__ = "funnel_config"

    stage: Mapped[int] = mapped_column(Integer, primary_key=True)
    prob: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SysDict(Base):
    """系统配置 · 数据字典（一级）。

    code 为可选固定编码，供前端按编码取字典（如车辆型号 = vehicle_model），无编码时仅按 id 维护。
    """

    __tablename__ = "sys_dict"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # 字典名称
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    items: Mapped[list["SysDictItem"]] = relationship(
        "SysDictItem", back_populates="dict", cascade="all, delete-orphan"
    )


class SysDictItem(Base):
    """系统配置 · 数据字典枚举值（二级）。"""

    __tablename__ = "sys_dict_item"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    dict_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("sys_dict.id"),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(String(128), nullable=False)  # 枚举值
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 排序（升序）
    dict: Mapped["SysDict"] = relationship("SysDict", back_populates="items")
