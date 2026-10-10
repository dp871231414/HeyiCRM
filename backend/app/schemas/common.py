"""通用响应模型。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Message(BaseModel):
    ok: bool = True
    msg: str = ""


class Data(BaseModel, Generic[T]):
    data: T


class ItemResult(BaseModel):
    ok: bool = True
    msg: str = ""
    data: dict[str, Any] | None = None


class ImportErrorItem(BaseModel):
    row: int
    field: str
    msg: str


class ImportResult(BaseModel):
    imported: int
    errors: list[ImportErrorItem] = []
