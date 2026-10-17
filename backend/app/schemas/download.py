"""下载中心相关模型。"""
from __future__ import annotations

from pydantic import BaseModel


class DownloadRecordOut(BaseModel):
    id: int
    objectType: str
    filename: str
    createdById: str = ""
    createdByName: str = ""
    createdAt: str = ""
