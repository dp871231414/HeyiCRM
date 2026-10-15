"""主任务（原「任务分类」）路由：列表、新增、改名。

主任务单独建表存储，支持下拉选择与动态新增：
- 列表：返回全部主任务（含系统默认「空」），供前端下拉使用；
- 新增：生成不可变 ID，记录创建人 / 创建时间；
- 改名：仅改 name，ID 不变（主任务名称可修改，ID 锁定）。
权限复用任务的 task.view / task.edit。
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_perm
from app.db.session import get_db
from app.models import MainTask, User
from app.services.serializers import org_name

router = APIRouter(prefix="/main-tasks", tags=["主任务"])

MT_NONE_ID = "MT_NONE"


class MainTaskOut(BaseModel):
    id: str
    name: str
    createdAt: str = ""
    createdBy: str = ""
    createdByName: str = ""
    # 责任人 / 责任部门：主任务首次被任务选用时从任务回填，下拉展示「名称 创建人」用 createdByName，
    # 这两个字段供「主任务单独维护」的数据表呈现（id 不可变，改名只改 name）。
    ownerId: str = ""
    ownerName: str = ""
    deptId: str = ""
    deptName: str = ""
    updatedAt: str = ""
    isSystem: bool = False


class MainTaskCreate(BaseModel):
    name: str = ""


class MainTaskRename(BaseModel):
    name: str = ""


def _next_id(db: Session) -> str:
    rows = db.scalars(select(MainTask.id)).all()
    max_seq = 0
    for mid in rows:
        m = re.fullmatch(r"MT(\d+)", mid or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"MT{max_seq + 1:04d}"


def _to_out(db: Session, mt: MainTask) -> MainTaskOut:
    creator_name = ""
    if mt.created_by:
        u = db.get(User, mt.created_by)
        creator_name = u.name if u else ""
    owner_name = ""
    if mt.owner_id:
        u = db.get(User, mt.owner_id)
        owner_name = u.name if u else ""
    dept_name = org_name(db, mt.dept_id) if mt.dept_id else ""
    return MainTaskOut(
        id=mt.id,
        name=mt.name,
        createdAt=mt.created_at.isoformat() if mt.created_at else "",
        createdBy=mt.created_by or "",
        createdByName=creator_name,
        ownerId=mt.owner_id or "",
        ownerName=owner_name,
        deptId=mt.dept_id or "",
        deptName=dept_name,
        updatedAt=mt.updated_at.isoformat() if mt.updated_at else "",
        isSystem=bool(mt.is_system),
    )


@router.get("", response_model=list[MainTaskOut])
def list_main_tasks(db: Session = Depends(get_db), _: User = Depends(require_perm("task.view"))):
    rows = db.scalars(select(MainTask).order_by(MainTask.is_system.desc(), MainTask.name)).all()
    return [_to_out(db, r) for r in rows]


@router.post("", response_model=MainTaskOut, status_code=201)
def create_main_task(
    payload: MainTaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.edit")),
):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="主任务名称不能为空")
    if len(name) > 128:
        raise HTTPException(status_code=422, detail="主任务名称不能超过 128 个字符")
    if db.scalar(select(MainTask).where(MainTask.name == name)):
        raise HTTPException(status_code=409, detail=f"主任务「{name}」已存在")

    mt = MainTask(id=_next_id(db), name=name, created_by=user.id)
    db.add(mt)
    db.commit()
    db.refresh(mt)
    return _to_out(db, mt)


@router.patch("/{mt_id}", response_model=MainTaskOut)
def rename_main_task(
    mt_id: str,
    payload: MainTaskRename,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.edit")),
):
    mt = db.get(MainTask, mt_id)
    if not mt:
        raise HTTPException(status_code=404, detail="主任务不存在")
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="主任务名称不能为空")
    if len(name) > 128:
        raise HTTPException(status_code=422, detail="主任务名称不能超过 128 个字符")
    # ID 不变，仅改名称；名称唯一，需排除自身后查重
    dup = db.scalar(select(MainTask).where(MainTask.name == name, MainTask.id != mt_id))
    if dup:
        raise HTTPException(status_code=409, detail=f"主任务「{name}」已存在")
    mt.name = name
    db.commit()
    db.refresh(mt)
    return _to_out(db, mt)
