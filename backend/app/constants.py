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
        "items": [
            {"key": "dashboard.view", "label": "查看经营驾驶舱", "type": "menu"},
            {"key": "dashboard.config", "label": "配置市场项目转化概率", "type": "action"},
        ],
    },
    {
        "menu": "market",
        "label": "项目管理",
        "items": [
            {"key": "market.view", "label": "查看项目列表与详情", "type": "menu"},
            {"key": "market.detail", "label": "查看项目详情", "type": "action"},
            {"key": "market.edit", "label": "新建 / 编辑项目", "type": "action"},
            {"key": "market.import", "label": "批量导入项目", "type": "action"},
            {"key": "market.delete", "label": "删除项目", "type": "action"},
        ],
    },
    {
        "menu": "task",
        "label": "任务管理",
        "items": [
            {"key": "task.view", "label": "查看任务列表与详情", "type": "menu"},
            {"key": "task.detail", "label": "查看任务详情", "type": "action"},
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
            # 编辑权限按页面上的三块组织（公司整体目标 / 指标监控 / 项目公司指标），
            # 让「这个权限管页面哪一块」在角色配置界面一眼可见。
            # 三块各自独立：勾了哪一块就能编辑哪一块，没有隐含的全局前置权限。
            {
                "key": "metric.edit_company",
                "label": "维护公司整体目标",
                "type": "action",
                "group": "公司整体目标",
            },
            {"key": "metric.edit", "label": "维护监控指标", "type": "action", "group": "指标监控"},
            {
                "key": "metric.edit_project",
                "label": "维护项目公司指标",
                "type": "action",
                "group": "项目公司指标",
            },
            {"key": "project.create", "label": "新增项目公司", "type": "action", "group": "项目公司指标"},
            {"key": "project.edit", "label": "编辑项目公司", "type": "action", "group": "项目公司指标"},
            {"key": "project.delete", "label": "删除项目公司", "type": "action", "group": "项目公司指标"},
            # 不带 group：渲染时排在上述分组之后
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
            {"key": "account.import", "label": "批量导入账号", "type": "action", "group": "批量操作"},
            {"key": "account.delete", "label": "删除账号", "type": "action", "group": "批量操作"},
        ],
    },
    {
        "menu": "system",
        "label": "系统配置",
        "items": [
            {"key": "sys.config.view", "label": "查看系统配置（数据字典）", "type": "menu"},
            {"key": "sys.config.edit", "label": "维护数据字典", "type": "action"},
        ],
    },
    {
        "menu": "doc",
        "label": "文档中心",
        "items": [
            {"key": "doc.view", "label": "查看文档中心", "type": "menu"},
            {"key": "doc.edit", "label": "编辑文档（分组 / 标题 / 内容）", "type": "action"},
            {"key": "doc.create", "label": "新建文档", "type": "action"},
            {"key": "doc.sync", "label": "从源文件同步文档（管理员）", "type": "action"},
        ],
    },
    {
        "menu": "download",
        "label": "下载中心",
        "items": [
            {"key": "download.view", "label": "查看下载中心（导出记录）", "type": "menu"},
        ],
    },
]

ALL_PERM_KEYS: set[str] = {item["key"] for g in PERM_GROUPS for item in g["items"]}

# 所有用户默认拥有的权限点：升级新增权限时自动补进每个角色（含自定义角色，幂等）
# doc.view 默认授予所有人，使文档中心菜单对所有角色可见（分组可见范围再由 Role.doc_groups 控制）
DEFAULT_PERMS_FOR_ALL: list[str] = ["task.detail", "market.detail", "sys.config.view", "download.view", "doc.view"]

# 权限 key → 中文名（用于报错提示，让用户知道缺哪个权限）
PERM_LABELS: dict[str, str] = {item["key"]: item["label"] for g in PERM_GROUPS for item in g["items"]}

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
    "market": "market.view",
    "system": "sys.config.view",
    "doc": "doc.view",
}

# 市场项目阶段（漏斗层级）· stage 即标题中的百分比
MARKET_STAGES: list[dict] = [
    {"stage": 10, "label": "项目导入"},
    {"stage": 25, "label": "市场尽调"},
    {"stage": 50, "label": "初审通过"},
    {"stage": 75, "label": "联合评审通过"},
    {"stage": 90, "label": "签约落地"},
    {"stage": 100, "label": "交车/投运"},
]
MARKET_STAGE_VALUES: list[int] = [s["stage"] for s in MARKET_STAGES]

# 流失阶段：转化率固定 0%，**不计入销售漏斗**（漏斗仅取 MARKET_STAGES）；
# 仅在「车辆需求分析」模块作为筛选条件出现，置于「交车/投运」之后。
# stage 取 0 即「0% 转化」语义，与转化率配置解耦（漏斗转化率配置只覆盖 MARKET_STAGES）。
CHURN_STAGE: dict = {"stage": 0, "label": "流失"}
# 车辆需求分析筛选用阶段集合（MARKET_STAGES + 流失），顺序即筛选标签顺序
DEMAND_ANALYSIS_STAGES: list[dict] = MARKET_STAGES + [CHURN_STAGE]

# 允许作为「项目阶段」落库的全部取值：常规 6 阶段 + 流失（stage=0，0% 转化，仅用于标记项目已流失，不进销售漏斗）。
# 编辑/新建项目、导入均以此为准；销售漏斗与转化率配置仍只取 MARKET_STAGES。
ALL_PROJECT_STAGE_VALUES: list[int] = MARKET_STAGE_VALUES + [CHURN_STAGE["stage"]]

# 全部阶段「取值 → 名称」映射（含流失），用于列表/详情/导出展示 stageLabel。
ALL_PROJECT_STAGE_LABELS: dict[int, str] = {s["stage"]: s["label"] for s in DEMAND_ANALYSIS_STAGES}

MARKET_PROJECT_ID_PREFIX = "MP"

# 指标分组元数据
METRIC_GROUP_META: dict[str, dict] = {
    "annual": {"label": "年度目标", "desc": "公司级年度目标 · 累计完成值为截止当月累计"},
    "project": {"label": "项目公司目标", "desc": "按项目公司单独核算 · 累计完成值为截止当月累计"},
    "monitor": {"label": "监控指标", "desc": "无目标值 · 事故 / 故障 / 租金减免统计"},
}

# 全公司（根组织）ID · 公司整体指标的归属组织
COMPANY_ORG_ID = "CO"

# 系统默认市场部 ID · 按 ID 锁定，不可删除（名称可改、负责人可改）。
# 经营驾驶舱「市场项目概览」的二级部门筛选、项目管理负责人范围都以它为根。
DEFAULT_MARKET_DEPT_ID = "D01"

# 组织类型
ORG_TYPE_COMPANY = "company"
ORG_TYPE_DEPT = "dept"
ORG_TYPE_TEAM = "team"
ORG_TYPE_PROJECT = "project"

TASK_ID_PREFIX = "T"
