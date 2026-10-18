"""任务组（原「任务分类」）路由：列表、新增、改名、删除。

任务组单独建表存储，支持下拉选择与动态新增：
- 列表：返回全部任务组（含系统默认「空」），供前端下拉使用；
- 新增：生成不可变 ID，记录创建人 / 创建时间；**所属责任人（owner_id）取自新建任务界面选中的责任人**；
- 改名：仅改 name，ID 不变（任务组名称可修改，ID 锁定）；
- 删除：系统默认「空」不可删；有任务引用的任务组，删除前将引用任务回退到「空」。

**唯一性口径**：任务组以「名称 + 责任人」联合唯一 —— 同名但责任人不同的任务组允许并存
（例如「华东大区营收达成」可由不同责任人各持一份）。库级不再对 name 设唯一约束，由本路由校验。
权限复用任务的 task.view / task.edit。
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_perm
from app.db.session import get_db
from app.models import Task, TaskGroup, User
from app.services.serializers import org_name

router = APIRouter(prefix="/task-groups", tags=["任务组"])

TG_NONE_ID = "TG_NONE"
TG_NAME_MAX = 25


class TaskGroupOut(BaseModel):
    id: str
    name: str
    createdAt: str = ""
    createdBy: str = ""
    createdByName: str = ""
    # 责任人 / 责任部门：任务组首次被任务选用时从任务回填，或直接由新建任务界面选定；
    # 下拉展示「名称 责任人」用 ownerName。
    ownerId: str = ""
    ownerName: str = ""
    deptId: str = ""
    deptName: str = ""
    updatedAt: str = ""
    isSystem: bool = False


class TaskGroupCreate(BaseModel):
    name: str = Field(default="", min_length=1, max_length=TG_NAME_MAX, description="任务组名称（≤25字）")
    # 所属责任人（用户 ID）：新建任务组时取界面选中的责任人；为空则无责任人
    owner_id: str | None = Field(default=None, description="任务组所属责任人用户 ID")


class TaskGroupRename(BaseModel):
    name: str = Field(default="", min_length=1, max_length=TG_NAME_MAX, description="任务组名称（≤25字）")


def _next_id(db: Session) -> str:
    rows = db.scalars(select(TaskGroup.id)).all()
    max_seq = 0
    for mid in rows:
        m = re.fullmatch(r"TG(\d+)", mid or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"TG{max_seq + 1:04d}"


def _to_out(db: Session, mt: TaskGroup) -> TaskGroupOut:
    creator_name = ""
    if mt.created_by:
        u = db.get(User, mt.created_by)
        creator_name = u.name if u else ""
    owner_name = ""
    if mt.owner_id:
        u = db.get(User, mt.owner_id)
        owner_name = u.name if u else ""
    dept_name = org_name(db, mt.dept_id) if mt.dept_id else ""
    return TaskGroupOut(
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


@router.get("", response_model=list[TaskGroupOut])
def list_task_groups(db: Session = Depends(get_db), _: User = Depends(require_perm("task.view"))):
    rows = db.scalars(select(TaskGroup).order_by(TaskGroup.is_system.desc(), TaskGroup.name)).all()
    return [_to_out(db, r) for r in rows]


@router.post("", response_model=TaskGroupOut, status_code=201)
def create_task_group(
    payload: TaskGroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.edit")),
):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="任务组名称不能为空")
    if len(name) > TG_NAME_MAX:
        raise HTTPException(status_code=422, detail=f"任务组名称不能超过 {TG_NAME_MAX} 个字")
    # 责任人（用户 ID）：校验存在；为空表示无责任人，与「名称 + 空责任人」同类
    owner_id = payload.owner_id
    if owner_id:
        if not db.get(User, owner_id):
            raise HTTPException(status_code=422, detail="任务组所属责任人不存在")
    # 唯一性 = 名称 + 责任人（同名但责任人不同允许并存）
    dup = db.scalar(
        select(TaskGroup).where(TaskGroup.name == name, TaskGroup.owner_id.is_(None) if owner_id is None else TaskGroup.owner_id == owner_id)
    )
    if dup:
        raise HTTPException(status_code=409, detail=f"任务组「{name}」已存在（同名且责任人相同）")

    mt = TaskGroup(id=_next_id(db), name=name, created_by=user.id, owner_id=owner_id)
    db.add(mt)
    db.commit()
    db.refresh(mt)
    return _to_out(db, mt)


@router.patch("/{mt_id}", response_model=TaskGroupOut)
def rename_task_group(
    mt_id: str,
    payload: TaskGroupRename,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.edit")),
):
    mt = db.get(TaskGroup, mt_id)
    if not mt:
        raise HTTPException(status_code=404, detail="任务组不存在")
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="任务组名称不能为空")
    if len(name) > TG_NAME_MAX:
        raise HTTPException(status_code=422, detail=f"任务组名称不能超过 {TG_NAME_MAX} 个字")
    # ID 不变，仅改名称；唯一性 = 名称 + 责任人（排除自身后查重）
    dup = db.scalar(
        select(TaskGroup).where(
            TaskGroup.name == name,
            TaskGroup.id != mt_id,
            TaskGroup.owner_id.is_(None) if mt.owner_id is None else TaskGroup.owner_id == mt.owner_id,
        )
    )
    if dup:
        raise HTTPException(status_code=409, detail=f"任务组「{name}」已存在（同名且责任人相同）")
    mt.name = name
    db.commit()
    db.refresh(mt)
    return _to_out(db, mt)


@router.delete("/{mt_id}")
def delete_task_group(
    mt_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.edit")),
):
    """删除任务组。

    - 系统默认「空」不可删；
    - 有任务引用的任务组，删除前将引用任务回退到「空」（不删除任务，仅解除分组归属）。
    """
    mt = db.get(TaskGroup, mt_id)
    if not mt:
        raise HTTPException(status_code=404, detail="任务组不存在")
    if mt.is_system:
        raise HTTPException(status_code=400, detail="系统默认任务组不可删除")
    # 引用该任务组的任务回退到「空」
    ref_tasks = db.scalars(select(Task).where(Task.task_group_id == mt_id)).all()
    none_name = ""
    none = db.get(TaskGroup, TG_NONE_ID)
    if none:
        none_name = none.name
    for t in ref_tasks:
        t.task_group_id = TG_NONE_ID
        t.title = none_name  # 冗余任务组名随归属一并清空
    db.delete(mt)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": mt_id, "reassignedTasks": len(ref_tasks)}}
