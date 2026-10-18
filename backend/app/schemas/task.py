"""任务相关模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# 字段长度上限（与前端 input/maxlength、导入校验三处保持一致）
TASK_NAME_MAX = 40
DESC_MAX = 150
PROGRESS_MAX = 150


class TaskOut(BaseModel):
    id: str
    parent: str
    title: str | None = None
    # 任务组（原「任务分类」）：下拉选择，单独建表；不选择时默认关联系统「空」
    taskGroupId: str = ""
    taskGroupName: str = ""
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
    task_group_id: str | None = Field(default=None, description="任务组ID；不传则默认关联系统「空」")
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

    @field_validator("parent")
    @classmethod
    def _v_parent(cls, v: str) -> str:
        if len(v) > TASK_NAME_MAX:
            raise ValueError(f"任务名称不能超过 {TASK_NAME_MAX} 个字")
        return v

    @field_validator("description")
    @classmethod
    def _v_desc(cls, v: str) -> str:
        if len(v) > DESC_MAX:
            raise ValueError(f"任务描述不能超过 {DESC_MAX} 个字")
        return v

    @field_validator("note")
    @classmethod
    def _v_note(cls, v: str) -> str:
        if len(v) > PROGRESS_MAX:
            raise ValueError(f"任务进展不能超过 {PROGRESS_MAX} 个字")
        return v


class TaskUpdate(BaseModel):
    parent: str = Field(min_length=1, max_length=128)
    task_group_id: str | None = Field(default=None, description="任务组ID；不传则默认关联系统「空」")
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

    @field_validator("parent")
    @classmethod
    def _v_parent(cls, v: str) -> str:
        if len(v) > TASK_NAME_MAX:
            raise ValueError(f"任务名称不能超过 {TASK_NAME_MAX} 个字")
        return v

    @field_validator("description")
    @classmethod
    def _v_desc(cls, v: str) -> str:
        if len(v) > DESC_MAX:
            raise ValueError(f"任务描述不能超过 {DESC_MAX} 个字")
        return v


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

    @field_validator("content")
    @classmethod
    def _v_content(cls, v: str) -> str:
        if len(v) > PROGRESS_MAX:
            raise ValueError(f"任务进展不能超过 {PROGRESS_MAX} 个字")
        return v
