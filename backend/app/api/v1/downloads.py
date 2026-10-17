"""下载中心：导出记录列表 / 文件下载 / 删除。

导出文件由 `app.services.download` 统一落盘到 downloads 目录，记录只存文件名；
列表与文件下载、删除均按创建人隔离（仅本人可见可操作）。
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_perm
from app.db.session import get_db
from app.models import DownloadRecord, User
from app.schemas.download import DownloadRecordOut
from app.services.download import DOWNLOAD_DIR

router = APIRouter(prefix="/downloads", tags=["下载中心"])

_SHEET_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("", response_model=list[DownloadRecordOut])
def list_downloads(
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("download.view")),
):
    """当前用户本人的导出记录，按创建时间倒序。"""
    rows = (
        db.scalars(
            select(DownloadRecord)
            .where(DownloadRecord.created_by == user.id)
            .order_by(DownloadRecord.created_at.desc())
        )
        .all()
    )
    return [
        DownloadRecordOut(
            id=r.id,
            objectType=r.object_type,
            filename=r.filename,
            createdById=r.created_by,
            createdByName=user.name,
            createdAt=r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        )
        for r in rows
    ]


@router.get("/{record_id}/file")
def download_file(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("download.view")),
):
    """下载某条记录对应的导出文件（仅创建人可下载）。"""
    rec = db.get(DownloadRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    if rec.created_by != user.id:
        raise HTTPException(status_code=403, detail="仅创建人可下载该文件")
    path = DOWNLOAD_DIR / rec.filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件已不存在")
    return FileResponse(str(path), media_type=_SHEET_MIME, filename=rec.filename)


@router.delete("/{record_id}", status_code=204)
def delete_download(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("download.view")),
):
    """删除导出记录及其文件（仅创建人可删除）。"""
    rec = db.get(DownloadRecord, record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    if rec.created_by != user.id:
        raise HTTPException(status_code=403, detail="仅创建人可删除该记录")
    path = DOWNLOAD_DIR / rec.filename
    if path.is_file():
        try:
            os.remove(path)
        except OSError:
            pass
    db.delete(rec)
    db.commit()
    return None
