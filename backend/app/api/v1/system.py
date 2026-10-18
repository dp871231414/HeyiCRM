"""系统配置 · 数据字典路由。

提供字典（一级）与枚举值（二级）的增删改查；车辆型号 / 挂车型号等由字典维护，
前端按 code 取值填充项目需求子列表的下拉项。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.deps import require_perm
from app.db.session import get_db
from app.models import SysDict, SysDictItem, User
from app.schemas.system import (
    DictStatusIn,
    SysDictCreate,
    SysDictItemOut,
    SysDictOut,
    SysDictUpdate,
)

router = APIRouter(prefix="/system/dicts", tags=["系统配置·数据字典"])


def _to_dict(d: SysDict) -> SysDictOut:
    items = (
        d.items
        if d.items is not None
        else []
    )
    items_sorted = sorted(items, key=lambda x: (x.sort, x.id))
    return SysDictOut(
        id=d.id,
        code=d.code,
        name=d.name,
        status=d.status or "active",
        items=[SysDictItemOut(id=i.id, value=i.value, sort=i.sort) for i in items_sorted],
    )


@router.get("", response_model=list[SysDictOut])
def list_dicts(
    code: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("sys.config.view")),
):
    """列出全部字典（或按 code 过滤），含枚举值。"""
    q = select(SysDict)
    if code:
        q = q.where(SysDict.code == code)
    rows = db.scalars(q.order_by(SysDict.id)).all()
    return [_to_dict(d) for d in rows]


@router.post("", response_model=SysDictOut, status_code=201)
def create_dict(
    payload: SysDictCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("sys.config.edit")),
):
    if payload.code:
        exist = db.scalar(select(SysDict).where(SysDict.code == payload.code))
        if exist:
            raise HTTPException(status_code=422, detail=f"编码 {payload.code} 已存在")
    d = SysDict(name=payload.name.strip(), code=payload.code)
    db.add(d)
    db.flush()
    for it in payload.items:
        db.add(SysDictItem(dict_id=d.id, value=it.value.strip(), sort=it.sort))
    db.commit()
    db.refresh(d)
    return _to_dict(d)


@router.patch("/{dict_id}", response_model=SysDictOut)
def update_dict(
    dict_id: int,
    payload: SysDictUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("sys.config.edit")),
):
    d = db.get(SysDict, dict_id)
    if not d:
        raise HTTPException(status_code=404, detail="字典不存在")
    if payload.code and payload.code != d.code:
        exist = db.scalar(select(SysDict).where(SysDict.code == payload.code, SysDict.id != dict_id))
        if exist:
            raise HTTPException(status_code=422, detail=f"编码 {payload.code} 已存在")
    d.name = payload.name.strip()
    d.code = payload.code
    # 枚举值整份替换：先删后插（编辑界面可增删多行）
    db.execute(delete(SysDictItem).where(SysDictItem.dict_id == d.id))
    for it in payload.items:
        db.add(SysDictItem(dict_id=d.id, value=it.value.strip(), sort=it.sort))
    db.commit()
    db.refresh(d)
    return _to_dict(d)


@router.post("/{dict_id}/status", response_model=SysDictOut)
def set_dict_status(
    dict_id: int,
    payload: DictStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("sys.config.edit")),
):
    """启用/停用字典：已存在的配置不允许删除，只能停用（停用后其枚举值不再出现在关联下拉中）。"""
    if payload.status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="status 仅支持 active / disabled")
    d = db.get(SysDict, dict_id)
    if not d:
        raise HTTPException(status_code=404, detail="字典不存在")
    d.status = payload.status
    db.commit()
    db.refresh(d)
    return _to_dict(d)
