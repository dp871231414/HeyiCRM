"""模型注册 · 导入全部模型，保证 Base.metadata 完整。"""
from app.db.base import Base
from app.models.log import MainTask, OperationLog, Task, TaskProgress
from app.models.metric import MetricActual, MetricDef, MetricTarget
from app.models.organization import Organization
from app.models.project import FunnelConfig, MarketProject, ProjectProgress
from app.models.user import Role, User

__all__ = [
    "Base",
    "Organization",
    "MetricDef",
    "MetricTarget",
    "MetricActual",
    "Task",
    "MainTask",
    "MarketProject",
    "ProjectProgress",
    "FunnelConfig",
    "Role",
    "User",
    "OperationLog",
    "TaskProgress",
]
