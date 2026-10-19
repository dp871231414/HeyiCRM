"""系统配置 · 文档中心。

文档内容存于数据库（system_doc 表），供「文档中心」菜单读取并渲染。
每次迭代把 docs/ 复制到 backend/bundled_docs/ 后调用 /sync 刷新数据库内容。

权限模型（两级）：
1) 菜单级：doc.view —— 决定能否进入文档中心；
2) 分组级：Role.doc_groups —— 决定能看哪些分组的文档（为空=全部分组）。
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.deps import get_user_perms, require_perm
from app.db.session import get_db
from app.docs_meta import DOC_BUNDLES, DOC_GROUPS, DOC_ORDER, DOC_TITLES, read_bundle, render_html
from app.models import Role, SystemDoc, User
from app.schemas.system import SystemDocCreate, SystemDocOut, SystemDocUpdate

router = APIRouter(prefix="/system/docs", tags=["系统配置·文档中心"])


def _out(doc: SystemDoc) -> SystemDocOut:
    return SystemDocOut(
        key=doc.doc_key,
        title=doc.title,
        fmt=doc.fmt,
        content=doc.content,
        html=render_html(doc.content, doc.fmt),
        group=doc.doc_group,
        version=doc.version,
        updated_at=doc.updated_at,
    )


def _allowed_groups(user: User, db) -> set | None:
    """返回当前用户可查看的文档分组集合；None 表示「全部分组」（管理员 / 未限定范围）。

    Role.doc_groups 为空代表不设限（看全部）；非空则只返回这些分组。
    """
    role = db.get(Role, user.role_id)
    if not role:
        return set()  # 无角色：看不到任何分组（兜底拒绝）
    groups = role.doc_groups or []
    if not groups:
        return None  # 全部分组
    return set(groups)


def _filter_by_group(docs: list[SystemDoc], allowed: set | None) -> list[SystemDoc]:
    if allowed is None:
        return docs
    return [d for d in docs if d.doc_group in allowed]


@router.get("", response_model=list[SystemDocOut])
def list_docs(db=Depends(get_db), user: User = Depends(require_perm("doc.view"))):
    """列出当前角色可见分组的全部文档（含渲染后的 html）。"""
    docs = db.scalars(select(SystemDoc).order_by(SystemDoc.id)).all()
    docs = _filter_by_group(docs, _allowed_groups(user, db))
    return [_out(d) for d in docs]


@router.get("/{key}", response_model=SystemDocOut)
def get_doc(key: str, db=Depends(get_db), user: User = Depends(require_perm("doc.view"))):
    d = db.scalar(select(SystemDoc).where(SystemDoc.doc_key == key))
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    allowed = _allowed_groups(user, db)
    if allowed is not None and d.doc_group not in allowed:
        raise HTTPException(status_code=404, detail="文档不存在或无权查看该分组")
    return _out(d)


@router.put("/{key}", response_model=SystemDocOut)
def update_doc(
    key: str,
    payload: SystemDocUpdate,
    db=Depends(get_db),
    user: User = Depends(require_perm("doc.edit")),
):
    """编辑文档（doc.edit）。content 改变时 version 自动 +1；可改分组/标题，doc_key 不变。"""
    d = db.scalar(select(SystemDoc).where(SystemDoc.doc_key == key))
    if not d:
        raise HTTPException(status_code=404, detail="文档不存在")
    if payload.title is not None:
        d.title = payload.title
    if payload.fmt is not None:
        d.fmt = payload.fmt
    if payload.group is not None:
        d.doc_group = payload.group
    if payload.content is not None:
        d.content = payload.content
        d.version += 1
    d.updated_by = user.id
    db.commit()
    db.refresh(d)
    return _out(d)


@router.post("", response_model=SystemDocOut, status_code=201)
def create_doc(
    payload: SystemDocCreate,
    db=Depends(get_db),
    user: User = Depends(require_perm("doc.create")),
):
    """新建文档（doc.create）。key 省略时自动生成；每个文档必须有分组，缺省归入「默认文档」。"""
    key = payload.key
    if not key:
        # 退化为 doc_<8位hex>，避免要求前端构造 slug
        key = "doc_" + uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[a-z0-9_]{1,32}", key):
        raise HTTPException(status_code=400, detail="文档 key 只能包含小写字母、数字、下划线，长度 1-32")
    if db.scalar(select(SystemDoc).where(SystemDoc.doc_key == key)):
        raise HTTPException(status_code=409, detail=f"文档 key「{key}」已存在")
    d = SystemDoc(
        doc_key=key,
        title=payload.title,
        fmt=payload.fmt or "markdown",
        doc_group=payload.group or "默认文档",
        content=payload.content or "",
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return _out(d)


@router.post("/sync", response_model=dict)
def sync_docs(db=Depends(get_db), user: User = Depends(require_perm("doc.sync"))):
    """从 backend/bundled_docs/ 读取最新源文件覆盖写入数据库（每次迭代自动更新用）。

    找不到源文件的文档跳过（不删除已有内容）。内置文档的分组按 DOC_GROUPS 统一维护。
    """
    synced = 0
    for key in DOC_ORDER:
        content = read_bundle(key)
        if content is None:
            continue
        fmt = DOC_BUNDLES.get(key, (None, "markdown"))[1]
        d = db.scalar(select(SystemDoc).where(SystemDoc.doc_key == key))
        if not d:
            d = SystemDoc(
                doc_key=key,
                title=DOC_TITLES.get(key, key),
                fmt=fmt,
                doc_group=DOC_GROUPS.get(key, "默认文档"),
                content=content,
            )
            db.add(d)
        else:
            d.content = content
            d.fmt = fmt
            d.version += 1
            # 内置文档分组由 DOC_GROUPS 统一维护，确保「设计文档合并入技术文档」等结构调整落地
            if key in DOC_GROUPS:
                d.doc_group = DOC_GROUPS[key]
        d.updated_by = user.id
        synced += 1
    db.commit()
    return {"ok": True, "synced": synced}
