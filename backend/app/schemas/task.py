"""任务相关模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: str
    parent: str
    title: str | None = None
    # 主任务（原「任务分类」）：下拉选择，单独建表；不选择时默认关联系统「空」
    mainTaskId: str = ""
    mainTaskName: str = ""
    description: str = ""
    abnormal: bool = False
    target: float
    done: float
    unit: str = ""
    note: str = ""
    startDate: str
    endDate: str
    deptId: str
    deptName: str = ""
    owner: str
    ownerId: str = ""
    progress: int = 0
    daysLeft: int | None = None
    statusLevel: str = "normal"
    statusLabel: str = "正常"
    # 系统自动记录，只读（不接受前端写入）
    createdById: str = ""
    createdByName: str = ""
    createdAt: str = ""
    updatedAt: str = ""


class TaskCreate(BaseModel):
    parent: str = Field(min_length=1, max_length=128, description="任务名称")
    main_task_id: str | None = Field(default=None, description="主任务ID；不传则默认关联系统「空」")
    description: str = ""
    abnormal: bool = False
    target: float = Field(gt=0)
    done: float = Field(ge=0)
    unit: str = ""
    note: str = ""
    start_date: str
    end_date: str
    dept_id: str
    owner: str


class TaskUpdate(BaseModel):
    parent: str = Field(min_length=1, max_length=128)
    main_task_id: str | None = Field(default=None, description="主任务ID；不传则默认关联系统「空」")
    description: str = ""
    abnormal: bool = False
    target: float = Field(gt=0)
    done: float = Field(ge=0)
    unit: str = ""
    note: str = ""
    start_date: str
    end_date: str
    dept_id: str
    owner: str


class TaskListOut(BaseModel):
    items: list[TaskOut]
    total: int
    page: int
    size: int


class DeptTaskStat(BaseModel):
    deptId: str
    deptName: str
    total: int
    done: int
    overdue: int
    risk: int
    dueSoon: int
    completion: int
