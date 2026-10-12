"""业务常量 · 权限清单、可见范围、指标分组元数据。

前端角色编辑界面直接消费 `/api/v1/permissions` 返回的本清单，保证前后端权限 key 一致。
"""
from __future__ import annotations

# 数据可见范围（四类）
SCOPES: dict[str, str] = {
    "self": "本人",
    "dept": "本部门",
    "dept_sub": "本部门及下属部门",
    "all": "全公司",
}

# 权限清单：菜单权限 + 按钮权限
PERM_GROUPS: list[dict] = [
    {
        "menu": "dashboard",
        "label": "经营驾驶舱",
        "items": [{"key": "dashboard.view", "label": "查看经营驾驶舱", "type": "menu"}],
    },
    {
        "menu": "task",
        "label": "任务管理",
        "items": [
            {"key": "task.view", "label": "查看任务列表与详情", "type": "menu"},
            {"key": "task.edit", "label": "新建 / 编辑任务", "type": "action"},
            {"key": "task.delete", "label": "删除任务", "type": "action"},
            {"key": "task.import", "label": "批量导入任务", "type": "action"},
        ],
    },
    {
        "menu": "metric",
        "label": "指标维护",
        "items": [
            {"key": "metric.view", "label": "查看指标数据", "type": "menu"},
            {"key": "metric.edit", "label": "录入 / 修改指标", "type": "action"},
            {"key": "metric.edit_company", "label": "维护公司整体目标", "type": "action"},
            {"key": "metric.edit_project", "label": "维护项目公司指标", "type": "action"},
            {"key": "project.create", "label": "新增项目公司", "type": "action"},
            {"key": "project.edit", "label": "编辑项目公司", "type": "action"},
            {"key": "project.delete", "label": "删除项目公司", "type": "action"},
            {"key": "metric.import", "label": "批量导入指标", "type": "action"},
        ],
    },
    {
        "menu": "account",
        "label": "账号管理",
        "items": [
            {"key": "account.view", "label": "查看账号与组织", "type": "menu"},
            {"key": "account.edit", "label": "新建 / 编辑账号与组织", "type": "action"},
            {"key": "account.role", "label": "角色与权限配置", "type": "action"},
        ],
    },
]

ALL_PERM_KEYS: set[str] = {item["key"] for g in PERM_GROUPS for item in g["items"]}

# 权限 → 归属菜单（用于「取消菜单权限时联动取消按钮权限」）
PERM_TO_MENU: dict[str, str] = {
    item["key"]: g["menu"] for g in PERM_GROUPS for item in g["items"]
}

# 页面 → 所需菜单权限（前端路由守卫与后端校验共用）
PAGE_PERM: dict[str, str] = {
    "dashboard": "dashboard.view",
    "tasks": "task.view",
    "metrics": "metric.view",
    "accounts": "account.view",
}

# 指标分组元数据
METRIC_GROUP_META: dict[str, dict] = {
    "annual": {"label": "年度目标", "desc": "公司级年度目标 · 累计完成值为截止当月累计"},
    "project": {"label": "项目公司目标", "desc": "按项目公司单独核算 · 累计完成值为截止当月累计"},
    "monitor": {"label": "监控指标", "desc": "无目标值 · 事故 / 故障 / 租金减免统计"},
}

# 全公司（根组织）ID · 公司整体指标的归属组织
COMPANY_ORG_ID = "CO"

# 组织类型
ORG_TYPE_COMPANY = "company"
ORG_TYPE_DEPT = "dept"
ORG_TYPE_TEAM = "team"
ORG_TYPE_PROJECT = "project"

TASK_ID_PREFIX = "T"
