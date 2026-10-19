"""系统配置 · 数据字典与文档中心相关模型。"""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SysDictItemIn(BaseModel):
    """字典枚举值（新增 / 编辑时携带）。"""

    value: str = Field(min_length=1, max_length=128, description="枚举值")
    sort: int = Field(default=0, description="排序（升序）")


class SysDictCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="字典名称")
    code: str | None = Field(default=None, max_length=64, description="固定编码（前端按编码取值，可选）")
    items: list[SysDictItemIn] = Field(default_factory=list, description="字典枚举值列表")


class SysDictUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="字典名称")
    code: str | None = Field(default=None, max_length=64, description="固定编码（可选）")
    items: list[SysDictItemIn] = Field(default_factory=list, description="字典枚举值列表（整份替换）")


class SysDictItemOut(BaseModel):
    id: int
    value: str
    sort: int


class SysDictOut(BaseModel):
    id: int
    code: str | None = None
    name: str
    status: str = "active"
    items: list[SysDictItemOut] = []


class DictStatusIn(BaseModel):
    """启用/停用切换（已存在的配置不允许删除，只能停用）。"""

    status: str = Field(description="active=启用 / disabled=停用")


class SystemDocOut(BaseModel):
    """文档中心文档输出（html 为已渲染的可 v-html 内容）。"""

    key: str
    title: str
    fmt: str = "markdown"
    content: str = ""
    html: str | None = None
    group: str = "默认文档"
    version: int = 1
    updated_at: datetime | None = None


class SystemDocUpdate(BaseModel):
    """文档更新入参（content 改变时版本号自动 +1；可改分组/标题，doc_key 不变）。"""

    title: str | None = None
    fmt: str | None = None
    content: str | None = None
    group: str | None = None


class SystemDocCreate(BaseModel):
    """新建文档入参。key 省略时由后端自动生成；每个文档必须有分组，缺省归入「默认文档」。"""

    key: str | None = Field(default=None, max_length=32, description="文档 key（唯一标识，省略则自动生成）")
    title: str = Field(min_length=1, max_length=128, description="文档标题")
    fmt: str = Field(default="markdown", description="markdown | html")
    content: str = Field(default="", description="文档内容")
    group: str = Field(default="默认文档", max_length=32, description="文档分组（来自数据字典 doc_group）")

    @field_validator("key")
    @classmethod
    def _check_key(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"[a-z0-9_]{1,32}", v):
            raise ValueError("文档 key 只能包含小写字母、数字、下划线，长度 1-32")
        return v
