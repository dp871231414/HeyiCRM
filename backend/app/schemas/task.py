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
    # 最新一条进展记录内容（冗余快照 = task.note），列表「进展描述」列展示用
    latestProgress: str = ""
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
    # 进展描述：创建时必填，作为该任务的第一条进展记录
    note: str = Field(min_length=1, description="进展描述（必填，写入第一条进展记录）")
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
    # 编辑界面不再直接改进展描述（只能通过「新增进展」追加记录），后端忽略该字段
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


class TaskProgressItem(BaseModel):
    id: int
    content: str
    createdById: str = ""
    createdByName: str = ""
    createdAt: str = ""


class TaskProgressListOut(BaseModel):
    items: list[TaskProgressItem]
    total: int
    page: int
    size: int


class TaskProgressCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000, description="本次进展内容")
