"""下载中心：导出文件落盘与记录创建（导出端点与下载中心路由共用）。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import DownloadRecord, User

# 导出文件统一落盘目录（默认 backend/downloads，随 start.sh 的工作目录解析）
DOWNLOAD_DIR = Path(settings.download_dir).resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 对象类型 → 文件名前缀（自动命名用）
_OBJECT_LABELS: dict[str, str] = {
    "task": "重点任务",
    "market_project": "市场项目",
}


def create_download_record(
    db: Session, user: User, object_type: str, content: bytes
) -> DownloadRecord:
    """落盘导出文件并写入一条下载中心记录（调用方负责 commit）。

    文件名按「对象标识 + 时间」自动生成，同一秒重复导出时追加序号避免覆盖。
    """
    label = _OBJECT_LABELS.get(object_type, object_type)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{label}_{ts}.xlsx"
    n = 1
    while (DOWNLOAD_DIR / filename).exists():
        filename = f"{label}_{ts}_{n}.xlsx"
        n += 1
    (DOWNLOAD_DIR / filename).write_bytes(content)

    rec = DownloadRecord(object_type=object_type, filename=filename, created_by=user.id)
    db.add(rec)
    return rec
