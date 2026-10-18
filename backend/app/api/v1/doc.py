"""系统配置 · 文档中心。

文档内容存于数据库（system_doc 表），供「使用说明」等菜单读取并渲染。
每次迭代把 docs/ 复制到 backend/bundled_docs/ 后调用 /sync 刷新数据库内容。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.deps import require_perm
from app.db.session import get_db
from app.docs_meta import DOC_BUNDLES, DOC_ORDER, DOC_TITLES, read_bundle, render_html
from app.models import SystemDoc, User
from app.schemas.system import SystemDocOut, SystemDocUpdate

router = APIRouter(prefix="/system/docs", tags=["系统配置·文档中心"])


def _out(doc: SystemDoc) -> SystemDocOut:
    return SystemDocOut(
        key=doc.doc_key,
        title=doc.title,
        fmt=doc.fmt,
        content=doc.content,
        html=render_html(doc.content, doc.fmt),
        version=doc.version,
        updated_at=doc.updated_at,
    )


@router.get("", response_model=list[SystemDocOut])
def list_docs(db=Depends(get_db), user: User = Depends(require_perm("sys.config.view"))):
    """列出全部文档（含渲染后的 html）。"""
    docs = db.scalars(select(SystemDoc).order_by(SystemDoc.id)).all()
    return [_out(d) for d in docs]


@router.get("/{key}", response_model=SystemDocOut)
def get_doc(key: str, db=Depends(get_db), user: User = Depends(require_perm("sys.config.view"))):
    d = db.scalar(select(SystemDoc).where(SystemDoc.doc_key == key))
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    return _out(d)


@router.put("/{key}", response_model=SystemDocOut)
def update_doc(
    key: str,
    payload: SystemDocUpdate,
    db=Depends(get_db),
    user: User = Depends(require_perm("sys.config.edit")),
):
    """编辑文档（仅管理员）。content 改变时 version 自动 +1。"""
    d = db.scalar(select(SystemDoc).where(SystemDoc.doc_key == key))
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    if payload.title is not None:
        d.title = payload.title
    if payload.fmt is not None:
        d.fmt = payload.fmt
    if payload.content is not None:
        d.content = payload.content
        d.version += 1
    d.updated_by = user.id
    db.commit()
    db.refresh(d)
    return _out(d)


@router.post("/sync", response_model=dict)
def sync_docs(db=Depends(get_db), user: User = Depends(require_perm("sys.config.edit"))):
    """从 backend/bundled_docs/ 读取最新源文件覆盖写入数据库（每次迭代自动更新用）。

    找不到源文件的文档跳过（不删除已有内容）。
    """
    synced = 0
    for key in DOC_ORDER:
        content = read_bundle(key)
        if content is None:
            continue
        fmt = DOC_BUNDLES.get(key, (None, "markdown"))[1]
        d = db.scalar(select(SystemDoc).where(SystemDoc.doc_key == key))
        if not d:
            d = SystemDoc(doc_key=key, title=DOC_TITLES.get(key, key), fmt=fmt, content=content)
            db.add(d)
        else:
            d.content = content
            d.fmt = fmt
            d.version += 1
        d.updated_by = user.id
        synced += 1
    db.commit()
    return {"ok": True, "synced": synced}
