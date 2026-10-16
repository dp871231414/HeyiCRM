"""种子数据 · 初始化组织、指标、任务、角色与演示账号。

用法：
    python -m app.seed            # 幂等写入（已存在则跳过）
    python -m app.seed --reset    # 清空后重建
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_PERMS_FOR_ALL
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    MainTask,
    MarketProject,
    MetricActual,
    MetricDef,
    MetricTarget,
    OperationLog,
    Organization,
    ProjectProgress,
    Role,
    Task,
    TaskProgress,
    User,
)

# 系统默认主任务：任务未选择主任务时默认关联它（始终存在，id 固定不可变）
MT_NONE_ID = "MT_NONE"
MT_NONE_NAME = "空"

SEED_PASSWORD = os.getenv("SEED_PASSWORD", "123456")

ORGS = [
    ("CO", "全公司", "company", None, "陈志明"),
    ("D01", "市场部", "dept", "CO", "林雪"),
    ("D02", "资产部", "dept", "CO", "赵国强"),
    ("D03", "运营部", "dept", "CO", "陈志明"),
    ("D04", "补能部", "dept", "CO", "孙志刚"),
    ("D05", "技术支持部", "dept", "CO", "吴敏"),
    ("D06", "财务部", "dept", "CO", "王建国"),
    ("D07", "金融部", "dept", "CO", "王建国"),
    ("D08", "行政部", "dept", "CO", "刘雅"),
    ("D09", "人事部", "dept", "CO", "何欣"),
    ("D10", "数智化部", "dept", "CO", "周涛"),
    ("D11", "法务部", "dept", "CO", "—"),
    # 市场部的二级部门（经营驾驶舱「市场项目概览」筛选标签 + 项目管理负责人范围以此为准）。
    # 系统默认市场部 D01 按 ID 锁定不可删除，但其下二级部门可自由增删。
    ("D12", "市场1部", "team", "D01", "—"),
    ("D13", "市场2部", "team", "D01", "—"),
    ("PC1", "合一重卡运营公司", "project", "CO", "李强"),
    ("PC2", "合一补能运营公司", "project", "CO", "周敏"),
    ("PC3", "合一车辆租赁公司", "project", "CO", "高翔"),
]

METRIC_DEFS = [
    dict(id="REV_SALE", name="销售收入", unit="万元", group="annual", family="revenue", direction="positive", cycle="month", weight=20, warn=0.95, danger=0.85, rate_target=0.95, owner_org_id="D01", description="重卡销售口径确认收入，累计完成口径"),
    dict(id="COLL_SALE", name="销售收入回款", unit="万元", group="annual", family="collection", parent_id="REV_SALE", direction="positive", cycle="month", weight=0, owner_org_id="D06", description="销售收入对应累计回款，回款率=回款/销售收入累计完成值"),
    dict(id="REV_TRANS", name="运力收入", unit="万元", group="annual", family="revenue", direction="positive", cycle="month", weight=20, warn=0.95, danger=0.85, rate_target=0.95, owner_org_id="D03", description="运力运营服务收入，累计完成口径"),
    dict(id="COLL_TRANS", name="运力收入回款", unit="万元", group="annual", family="collection", parent_id="REV_TRANS", direction="positive", cycle="month", weight=0, owner_org_id="D06", description="运力收入对应累计回款"),
    dict(id="REV_ENER", name="补能收入", unit="万元", group="annual", family="revenue", direction="positive", cycle="month", weight=15, warn=0.95, danger=0.85, rate_target=0.95, owner_org_id="D03", description="充/换电、加气等补能服务收入，累计完成口径"),
    dict(id="COLL_ENER", name="补能收入回款", unit="万元", group="annual", family="collection", parent_id="REV_ENER", direction="positive", cycle="month", weight=0, owner_org_id="D06", description="补能收入对应累计回款"),
    dict(id="REV_LEAS", name="租赁收入", unit="万元", group="annual", family="revenue", direction="positive", cycle="month", weight=15, warn=0.95, danger=0.85, rate_target=0.95, owner_org_id="D03", description="车辆租赁业务收入，累计完成口径"),
    dict(id="COLL_LEAS", name="租赁收入回款", unit="万元", group="annual", family="collection", parent_id="REV_LEAS", direction="positive", cycle="month", weight=0, owner_org_id="D06", description="租赁收入对应累计回款"),
    dict(id="DIG_VEH", name="车辆消化", unit="辆", group="annual", family="digest", direction="positive", cycle="month", weight=15, warn=0.95, danger=0.85, owner_org_id="D01", description="年内累计消化（销售/投运）车辆数"),
    dict(id="DIG_TRL", name="挂车消化", unit="辆", group="annual", family="digest", direction="positive", cycle="month", weight=15, warn=0.95, danger=0.85, owner_org_id="D01", description="年内累计消化挂车数"),
    dict(id="OP_VEH", name="运营车辆", unit="辆", group="project", family="op", direction="positive", cycle="month", weight=30, warn=0.95, danger=0.85, is_snapshot=True, owner_org_id="D03", description="期末在营车辆数（期末快照，非累计）"),
    dict(id="OP_REV", name="运营收入", unit="万元", group="project", family="op", direction="positive", cycle="month", weight=40, warn=0.95, danger=0.85, rate_target=0.93, owner_org_id="D01", description="项目公司累计运营收入"),
    dict(id="OP_REV_COLL", name="运营收入回款", unit="万元", group="project", family="collection", parent_id="OP_REV", direction="positive", cycle="month", weight=0, owner_org_id="D06", description="项目公司运营收入对应累计回款"),
    dict(id="OP_PROFIT", name="运营利润", unit="万元", group="project", family="op", direction="positive", cycle="month", weight=30, warn=0.95, danger=0.85, owner_org_id="D06", description="项目公司累计运营利润"),
    dict(id="INC_TOT", name="总事故数", unit="起", group="monitor", family="incident", direction="negative", cycle="month", weight=0, no_target=True, description="当月发生的安全事故总数"),
    dict(id="INC_DOING", name="处理中事故数", unit="起", group="monitor", family="incident", direction="negative", cycle="month", weight=0, no_target=True, description="当月事故中尚未闭环的数量"),
    dict(id="INC_DONE", name="已处理事故数", unit="起", group="monitor", family="incident", direction="negative", cycle="month", weight=0, no_target=True, description="当月事故中已完成处理闭环的数量"),
    dict(id="INC_AMT", name="总事故金额", unit="万元", group="monitor", family="incident", direction="negative", cycle="month", weight=0, no_target=True, description="当月事故涉及的预计损失金额"),
    dict(id="FAU_TOT", name="总故障数", unit="起", group="monitor", family="fault", direction="negative", cycle="month", weight=0, no_target=True, description="当月车辆故障上报总数"),
    dict(id="FAU_DOING", name="处理中故障数", unit="起", group="monitor", family="fault", direction="negative", cycle="month", weight=0, no_target=True, description="当月故障中尚未修复完成的数量"),
    dict(id="FAU_DONE", name="已处理故障数", unit="起", group="monitor", family="fault", direction="negative", cycle="month", weight=0, no_target=True, description="当月故障中已完成修复的数量"),
    dict(id="FAU_AMT", name="总故障金额", unit="万元", group="monitor", family="fault", direction="negative", cycle="month", weight=0, no_target=True, description="当月故障涉及的维修与停运损失金额"),
    dict(id="RD_CNT", name="总租金减免次数", unit="次", group="monitor", family="rent", direction="negative", cycle="month", weight=0, no_target=True, description="当月批准的租金减免笔数"),
    dict(id="RD_AMT", name="总租金减免金额", unit="万元", group="monitor", family="rent", direction="negative", cycle="month", weight=0, no_target=True, description="当月批准的租金减免总金额"),
]

PERIODS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]

TARGETS = [
    ("REV_SALE", "2026", "CO", 12000), ("REV_TRANS", "2026", "CO", 26000),
    ("REV_ENER", "2026", "CO", 8600), ("REV_LEAS", "2026", "CO", 6400),
    ("DIG_VEH", "2026", "CO", 1200), ("DIG_TRL", "2026", "CO", 800),
    ("OP_VEH", "2026", "PC1", 600), ("OP_REV", "2026", "PC1", 18000), ("OP_PROFIT", "2026", "PC1", 1500),
    ("OP_VEH", "2026", "PC2", 320), ("OP_REV", "2026", "PC2", 5200), ("OP_PROFIT", "2026", "PC2", 620),
    ("OP_VEH", "2026", "PC3", 280), ("OP_REV", "2026", "PC3", 3400), ("OP_PROFIT", "2026", "PC3", 380),
]

SERIES = {
    ("REV_SALE", "CO"): [3120, 4180, 5460, 6690, 7860, 8900, 9860],
    ("COLL_SALE", "CO"): [2890, 3930, 5180, 6350, 7480, 8470, 9370],
    ("REV_TRANS", "CO"): [6800, 9150, 11980, 14720, 17300, 19480, 21320],
    ("COLL_TRANS", "CO"): [6390, 8650, 11320, 13990, 16440, 18510, 20250],
    ("REV_ENER", "CO"): [2280, 3020, 3960, 4900, 5780, 6620, 7390],
    ("COLL_ENER", "CO"): [2090, 2790, 3680, 4560, 5390, 6190, 6870],
    ("REV_LEAS", "CO"): [1650, 2230, 2950, 3660, 4290, 4900, 5480],
    ("COLL_LEAS", "CO"): [1350, 1850, 2480, 3090, 3650, 4160, 4610],
    ("DIG_VEH", "CO"): [260, 352, 458, 562, 668, 762, 1015],
    ("DIG_TRL", "CO"): [178, 240, 312, 384, 458, 522, 690],
    ("OP_VEH", "PC1"): [486, 508, 530, 552, 571, 588, 604],
    ("OP_REV", "PC1"): [4560, 6180, 8090, 9950, 11680, 13150, 15230],
    ("OP_REV_COLL", "PC1"): [4290, 5830, 7650, 9420, 11060, 12460, 14460],
    ("OP_PROFIT", "PC1"): [386, 522, 683, 842, 988, 1112, 1285],
    ("OP_VEH", "PC2"): [262, 272, 281, 289, 296, 302, 296],
    ("OP_REV", "PC2"): [1320, 1780, 2330, 2870, 3360, 3790, 4510],
    ("OP_REV_COLL", "PC2"): [1210, 1640, 2150, 2650, 3100, 3500, 4190],
    ("OP_PROFIT", "PC2"): [158, 213, 279, 343, 401, 453, 540],
    ("OP_VEH", "PC3"): [158, 166, 173, 179, 184, 189, 191],
    ("OP_REV", "PC3"): [860, 1160, 1520, 1870, 2190, 2470, 2780],
    ("OP_REV_COLL", "PC3"): [700, 950, 1250, 1540, 1810, 2050, 2280],
    ("OP_PROFIT", "PC3"): [98, 132, 173, 214, 250, 283, 315],
    ("INC_TOT", "CO"): [2, 1, 3, 2, 4, 2, 3],
    ("INC_DOING", "CO"): [0, 0, 1, 0, 1, 1, 1],
    ("INC_DONE", "CO"): [2, 1, 2, 2, 3, 1, 2],
    ("INC_AMT", "CO"): [28, 15, 42, 30, 55, 25, 45.2],
    ("FAU_TOT", "CO"): [21, 18, 24, 19, 26, 15, 17],
    ("FAU_DOING", "CO"): [6, 4, 7, 5, 8, 3, 5],
    ("FAU_DONE", "CO"): [15, 14, 17, 14, 18, 12, 12],
    ("FAU_AMT", "CO"): [32.5, 26.8, 38.2, 29.5, 41.0, 22.4, 28.6],
    ("RD_CNT", "CO"): [4, 3, 5, 4, 6, 3, 6],
    ("RD_AMT", "CO"): [21.5, 16.2, 28.8, 23.0, 34.6, 18.9, 38.5],
}

TASKS = [
    dict(id="T202601", parent="完成全年营收目标 10.2 亿", title="华东大区营收达成", description="华东大区年度营收承接，含新能源运力替换带来的增量收入", abnormal=False, target=46000, done=31800, unit="万元", note="Q3 累计 3.18 亿，进度略慢于时间轴", start="2026-01-01", end="2026-12-31", dept="D01", owner="郑凯"),
    dict(id="T202602", parent="完成全年营收目标 10.2 亿", title="华南大区营收达成", description="华南大区年度营收承接", abnormal=False, target=22000, done=15800, unit="万元", note="Q3 累计 1.58 亿，客户结构待优化", start="2026-01-01", end="2026-12-31", dept="D01", owner="何欣"),
    dict(id="T202603", parent="车队调度数字化系统上线", title="系统配置与 UAT 验收", description="调度系统配置、与现有车队系统集成、用户验收测试", abnormal=True, target=1, done=0, unit="项", note="UAT 第二轮回归，发现 12 个缺陷待修复", start="2026-09-01", end="2026-11-30", dept="D10", owner="陈志明"),
    dict(id="T202604", parent="单公里成本压降专项", title="轮胎与油耗专项优化", description="轮胎集中采购与油耗监控机制落地", abnormal=False, target=1, done=1, unit="项", note="已完成，单胎成本下降 6%", start="2026-07-01", end="2026-09-30", dept="D03", owner="王建国"),
    dict(id="T202605", parent="单公里成本压降专项", title="空驶率降至 12% 以下", description="通过调度优化降低空驶里程占比", abnormal=False, target=12, done=11.8, unit="%", note="当前空驶率 11.8%，已达标待复核", start="2026-08-01", end="2026-10-10", dept="D03", owner="王建国"),
    dict(id="T202606", parent="车辆完好率提升至 96% 以上", title="预防性检修制度落地", description="建立按里程触发的预防性检修计划", abnormal=False, target=1, done=1, unit="项", note="已完成，检修及时率 91%", start="2026-06-01", end="2026-08-31", dept="D05", owner="赵国强"),
    dict(id="T202607", parent="车辆完好率提升至 96% 以上", title="备件供应链优化", description="核心备件安全库存与供应商响应机制", abnormal=True, target=1, done=0, unit="项", note="备件到货周期仍超 72 小时，需更换供应商", start="2026-08-15", end="2026-10-08", dept="D02", owner="赵国强"),
    dict(id="T202608", parent="安全生产零事故年度目标", title="隐患整改闭环", description="安全隐患排查与整改闭环管理", abnormal=True, target=100, done=76, unit="项", note="本月发生 3 起轻微事故，需专项复盘", start="2026-07-01", end="2026-10-31", dept="D03", owner="孙志刚"),
    dict(id="T202609", parent="客户体验提升", title="重点客户回访覆盖", description="对 90 家重点客户完成一轮回访", abnormal=False, target=90, done=68, unit="家", note="已完成 68 家，剩余 22 家待安排", start="2026-09-01", end="2026-10-31", dept="D01", owner="刘雅"),
    dict(id="T202610", parent="应收账款清收专项", title="租赁回款专项清收", description="清理租赁业务 60 天以上账龄应收账款", abnormal=False, target=1200, done=640, unit="万元", note="租赁回款率 84.1% 偏低，需重点跟进 3 家大客户", start="2026-09-01", end="2026-11-30", dept="D07", owner="王建国"),
    dict(id="T202611", parent="华东大区新能源运力替换", title="首批新能源车辆投运", description="首批 30 辆新能源运输车投运", abnormal=True, target=30, done=12, unit="辆", note="牌照与充电桩审批滞后，已申请延期至 12 月", start="2026-08-01", end="2026-10-09", dept="D01", owner="郑凯"),
    dict(id="T202612", parent="调度优化", title="调度一班空驶率压降", description="调度一班空驶率降至 12% 以下", abnormal=False, target=12, done=11.8, unit="%", note="空驶率从 14% 降至 11.8%", start="2026-08-01", end="2026-10-25", dept="D03", owner="周涛"),
    dict(id="T202613", parent="调度优化", title="调度二班准点率提升", description="调度二班出车准点率提升至 94%", abnormal=False, target=94, done=94.2, unit="%", note="已完成，准点率 94.2%", start="2026-08-01", end="2026-09-30", dept="D03", owner="吴敏"),
    dict(id="T202614", parent="华南大区客户结构优化", title="高毛利客户画像分析", description="华南大区高毛利业务客户画像与拓展清单", abnormal=False, target=1, done=0, unit="项", note="待公司级目标下达后启动", start="2026-11-01", end="2026-12-15", dept="D01", owner="何欣"),
]

ROLES = [
    dict(id="admin", name="系统管理员", description="全部菜单与操作权限，可管理账号与角色", scope="all", is_system=True,
         permissions=["dashboard.view", "dashboard.config", "task.view", "task.detail", "task.edit", "task.delete", "task.import", "metric.view", "metric.edit", "metric.edit_company", "metric.edit_project", "project.create", "project.edit", "project.delete", "metric.import", "market.view", "market.detail", "market.edit", "market.import", "market.delete", "account.view", "account.edit", "account.role", "account.import", "account.delete"]),
    dict(id="dept_head", name="部门负责人", description="本部门及下属部门的任务与指标全权", scope="dept_sub", is_system=True,
         permissions=["dashboard.view", "task.view", "task.detail", "task.edit", "task.import", "metric.view", "metric.edit", "metric.edit_project", "metric.import", "market.view", "market.detail", "market.edit", "market.import"]),
    dict(id="member", name="普通成员", description="仅维护本人任务与指标", scope="self", is_system=True,
         permissions=["dashboard.view", "task.view", "task.detail", "task.edit", "metric.view", "metric.edit", "market.view", "market.detail", "market.edit"]),
]

# 市场项目（商机）演示数据 · 覆盖全部六个阶段，让漏斗每一层都有数
MARKET_PROJECTS = [
    dict(name="华东物流园运力替换项目", description="物流园 200 辆燃油重卡替换为新能源", tractor=200, trailer=120, stage=25, owner="郑凯"),
    dict(name="港口集疏运车队项目", description="港区短倒运输车队组建", tractor=80, trailer=80, stage=50, owner="林雪"),
    dict(name="钢铁厂大宗原料运输项目", description="原料进厂专线运力", tractor=60, trailer=60, stage=75, owner="郑凯"),
    dict(name="快递干线甩挂运输项目", description="干线甩挂，挂车配比 1:2", tractor=40, trailer=80, stage=90, owner="何欣"),
    dict(name="矿区短驳车队投运项目", description="矿区内部短驳，已签约", tractor=30, trailer=15, stage=100, owner="林雪"),
    dict(name="城配新能源示范项目", description="城市配送试点导入", tractor=25, trailer=0, stage=10, owner="周涛"),
    dict(name="冷链干线车队扩充项目", description="冷链干线增补运力", tractor=45, trailer=45, stage=25, owner="郑凯"),
    dict(name="煤炭运输长协项目", description="年度长协运力框架", tractor=100, trailer=100, stage=50, owner="王建国"),
]

USERS = [
    ("U001", "陈志明", "admin", "CO", "admin", "active"),
    ("U002", "林雪", "linxue", "D01", "dept_head", "active"),
    ("U003", "王建国", "wangjg", "D06", "dept_head", "active"),
    ("U004", "赵国强", "zhaogq", "D02", "dept_head", "active"),
    ("U005", "刘雅", "liuya", "D08", "dept_head", "active"),
    ("U006", "郑凯", "zhengkai", "D01", "member", "active"),
    ("U007", "何欣", "hexin", "D09", "member", "active"),
    ("U008", "周涛", "zhoutao", "D10", "member", "active"),
    ("U009", "吴敏", "wumin", "D05", "member", "active"),
    ("U010", "孙志刚", "sunzg", "D04", "dept_head", "active"),
    ("U011", "李明", "liming", "D06", "member", "disabled"),
    ("U012", "李强", "liqiang", "PC1", "dept_head", "active"),
    ("U013", "周敏", "zhoumin", "PC2", "dept_head", "active"),
    ("U014", "高翔", "gaoxiang", "PC3", "dept_head", "active"),
    # 市场部二级部门人员（与线上库一致，保证线上线下市场人员清单对齐）
    ("U015", "胡启迪", "huqidi", "D12", "dept_head", "active"),
    ("U016", "冯成志", "fengchengzhi", "D12", "member", "active"),
    ("U017", "周春泉", "zhouchunquan", "D13", "dept_head", "active"),
]


def _d(s: str) -> date:
    return date.fromisoformat(s)


# ---------------------------------------------------------------- 主任务（原「任务分类」）


def next_main_task_id(db: Session) -> str:
    """生成下一个主任务 ID：MT + 4 位自增序号（系统默认 MT_NONE 不参与序号）。"""
    rows = db.scalars(select(MainTask.id)).all()
    max_seq = 0
    for mid in rows:
        m = re.fullmatch(r"MT(\d+)", mid or "")
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"MT{max_seq + 1:04d}"


def get_or_create_main_task(db: Session, name: str, created_by: str | None = None) -> MainTask:
    """按名称取主任务，不存在则新建（名称唯一）。"""
    existing = db.scalar(select(MainTask).where(MainTask.name == name))
    if existing:
        return existing
    mt = MainTask(id=next_main_task_id(db), name=name, created_by=created_by)
    db.add(mt)
    db.flush()
    return mt


def ensure_main_task_none(db: Session) -> None:
    """确保系统默认主任务「空」(MT_NONE) 存在。"""
    if not db.scalar(select(MainTask).where(MainTask.id == MT_NONE_ID)):
        db.add(MainTask(id=MT_NONE_ID, name=MT_NONE_NAME, created_by=None, is_system=True))
        db.flush()


def backfill_task_main_tasks(db: Session) -> int:
    """数据迁移：把 main_task_id 为空的任务按原 title 回填主任务（幂等，仅处理空值）。

    升级旧库时，已有任务没有主任务关联；这里以原「任务分类」文本对应到主任务，
    文本为空则归到系统默认「空」。返回回填条数。
    """
    nulls = db.scalars(select(Task).where(Task.main_task_id.is_(None))).all()
    if not nulls:
        return 0
    for t in nulls:
        if t.title:
            t.main_task_id = get_or_create_main_task(db, t.title, created_by=t.created_by).id
        else:
            t.main_task_id = MT_NONE_ID
    return len(nulls)


def backfill_project_progress(db: Session) -> int:
    """数据迁移：把已有市场项目的「进展快照」(progress) 转为该项目的第一条进展记录（幂等）。

    仅处理「progress 非空且还没有任何进展记录」的项目；时间取项目更新时间，
    记录人取项目创建人。返回回填条数。（新库 progress 默认空串，通常为 0。）
    """
    # 会话 autoflush=False：seed 同事务里刚 add 的项目尚未落库，先 flush 保证查询可见
    db.flush()
    projects = db.scalars(select(MarketProject).where(MarketProject.progress != "")).all()
    if not projects:
        return 0
    has_records = {
        pid
        for (pid,) in db.execute(
            select(ProjectProgress.project_id).where(ProjectProgress.project_id.in_([p.id for p in projects]))
        ).all()
    }
    n = 0
    for p in projects:
        if p.id in has_records or not (p.progress or "").strip():
            continue
        db.add(
            ProjectProgress(
                project_id=p.id, content=p.progress, created_by=p.created_by,
                created_at=p.updated_at or p.created_at,
            )
        )
        n += 1
    return n


def backfill_task_progress(db: Session) -> int:
    """数据迁移：把已有任务的「进展描述」(note) 转为该任务的第一条进展记录（幂等）。

    仅处理「note 非空且还没有任何进展记录」的任务；时间取任务更新时间，
    记录人取任务创建人。返回回填条数。
    """
    # 会话 autoflush=False：seed 同事务里刚 add 的任务尚未落库，先 flush 保证查询可见
    db.flush()
    tasks = db.scalars(select(Task).where(Task.note != "")).all()
    if not tasks:
        return 0
    has_records = {
        tid
        for (tid,) in db.execute(
            select(TaskProgress.task_id).where(TaskProgress.task_id.in_([t.id for t in tasks]))
        ).all()
    }
    n = 0
    for t in tasks:
        if t.id in has_records or not (t.note or "").strip():
            continue
        db.add(
            TaskProgress(
                task_id=t.id, content=t.note, created_by=t.created_by,
                created_at=t.updated_at or t.created_at,
            )
        )
        n += 1
    return n


def backfill_main_task_owners(db: Session) -> int:
    """数据迁移：主任务责任人为空时，取其下最早创建的任务的责任人/部门回填（幂等）。

    与「首次被任务选用时回填」同一语义 —— 对升级前已存在的任务，视最早那条为首次选用。
    """
    db.flush()
    mts = db.scalars(select(MainTask).where(MainTask.is_system.is_(False), MainTask.owner_id.is_(None))).all()
    if not mts:
        return 0
    n = 0
    for mt in mts:
        first = db.scalar(
            select(Task).where(Task.main_task_id == mt.id).order_by(Task.id.asc()).limit(1)
        )
        if not first:
            continue
        u = db.scalar(select(User).where(User.name == (first.owner or "").strip()))
        mt.owner_id = u.id if u else None
        mt.dept_id = mt.dept_id or first.dept_id
        n += 1
    return n


def seed(db: Session, reset: bool = False) -> dict:
    if reset:
        for model in (OperationLog, MetricActual, MetricTarget, Task, MarketProject, User, Role, MetricDef, Organization):
            db.execute(delete(model))
        db.commit()

    created = {"orgs": 0, "metrics": 0, "targets": 0, "actuals": 0, "tasks": 0, "marketProjects": 0, "roles": 0, "users": 0, "roles_synced": 0}

    if not db.scalar(select(Organization).limit(1)):
        for i, (oid, name, otype, parent, head) in enumerate(ORGS):
            db.add(Organization(id=oid, name=name, type=otype, parent_id=parent, head=head, sort_order=i))
            created["orgs"] += 1

    if not db.scalar(select(MetricDef).limit(1)):
        for i, m in enumerate(METRIC_DEFS):
            db.add(MetricDef(sort_order=i, **m))
            created["metrics"] += 1

    if not db.scalar(select(Role).limit(1)):
        for r in ROLES:
            db.add(Role(**r))
            created["roles"] += 1
    else:
        # 内置角色的权限清单会随版本新增权限点（如 metric.edit_company / metric.edit_project）。
        # 已存在的库需要对齐一次，否则升级后拿不到新权限；自定义角色不受影响。
        for spec in ROLES:
            role = db.get(Role, spec["id"])
            if role is None or not role.is_system:
                continue
            if sorted(role.permissions or []) != sorted(spec["permissions"]):
                role.permissions = list(spec["permissions"])
                role.scope = spec["scope"]
                created["roles_synced"] += 1

    # 新增权限点默认授予所有用户：缺哪个补哪个（含自定义角色），幂等
    for role in db.scalars(select(Role)).all():
        missing = [p for p in DEFAULT_PERMS_FOR_ALL if p not in (role.permissions or [])]
        if missing:
            role.permissions = list(role.permissions or []) + missing
            created.setdefault("perms_granted", {}).setdefault(role.id, []).extend(missing)

    # 是否「首次初始化」：库里连一个账号都没有。
    # 演示数据只在首次初始化时灌入 —— 否则管理员清空任务后，服务重启会把数据"复活"。
    # 注意必须在灌账号之前取值（之后 add 的记录会被 autoflush 查到）。
    first_init = not db.scalar(select(User).limit(1))

    if first_init:
        pwd = hash_password(SEED_PASSWORD)
        for uid, name, account, dept, role, status in USERS:
            db.add(User(id=uid, name=name, account=account, password_hash=pwd, dept_id=dept, role_id=role, status=status))
            created["users"] += 1

    if not db.scalar(select(MetricTarget).limit(1)):
        for metric_id, period, org_id, value in TARGETS:
            db.add(MetricTarget(metric_id=metric_id, period=period, org_id=org_id, value=Decimal(str(value))))
            created["targets"] += 1

    if not db.scalar(select(MetricActual).limit(1)):
        for (metric_id, org_id), values in SERIES.items():
            for period, value in zip(PERIODS, values):
                db.add(MetricActual(metric_id=metric_id, org_id=org_id, period=period, value=Decimal(str(value)), created_by="U001"))
                created["actuals"] += 1

    # 任务同样只在首次初始化时灌入（见上：清空后不应被重启"复活"）
    ensure_main_task_none(db)
    if first_init and not db.scalar(select(Task).limit(1)):
        # 演示任务各自的「任务分类」对应为主任务（按名称建表），建立 名称→id 映射
        title_to_mt: dict[str, str] = {}
        for t in TASKS:
            title = t["title"]
            if title and title not in title_to_mt:
                title_to_mt[title] = get_or_create_main_task(db, title, created_by="U001").id
        for t in TASKS:
            mt_id = title_to_mt.get(t["title"]) or MT_NONE_ID
            db.add(
                Task(
                    id=t["id"], parent=t["parent"], title=t["title"], main_task_id=mt_id,
                    description=t["description"],
                    abnormal=t["abnormal"], target=Decimal(str(t["target"])), done=Decimal(str(t["done"])),
                    unit=t["unit"], note=t["note"], start_date=_d(t["start"]), end_date=_d(t["end"]),
                    dept_id=t["dept"], owner=t["owner"], created_by="U001",
                )
            )
            created["tasks"] += 1

    # 数据迁移：升级旧库时，把 main_task_id 为空的任务按原「任务分类」回填主任务
    created["mainTasksBackfilled"] = backfill_task_main_tasks(db)

    # 数据迁移：升级旧库时，把已有任务的「进展描述」转为第一条进展记录
    created["progressBackfilled"] = backfill_task_progress(db)

    # 数据迁移：把已有市场项目的「进展快照」转为第一条进展记录
    created["projectProgressBackfilled"] = backfill_project_progress(db)

    # 数据迁移：主任务责任人/部门为空时，取其下最早任务回填（下拉「名称 责任人」展示用）
    created["mainTaskOwnersBackfilled"] = backfill_main_task_owners(db)

    # 市场项目同理：只在首次初始化时灌入演示数据
    if first_init and not db.scalar(select(MarketProject).limit(1)):
        for i, mp in enumerate(MARKET_PROJECTS, start=1):
            db.add(
                MarketProject(
                    id=f"MP{i:04d}", name=mp["name"], description=mp["description"],
                    tractor_demand=mp["tractor"], trailer_demand=mp["trailer"],
                    stage=mp["stage"], owner=mp["owner"], created_by="U001",
                )
            )
            created["marketProjects"] += 1

    db.commit()
    return created


def main() -> None:
    reset = "--reset" in sys.argv
    Base.metadata.create_all(bind=engine)
    # 兼容已上线但模型后续新增列的旧库：create_all 只建表不补列，这里对缺失列做一次 ALTER。
    # 必须放在 seed 之前 —— start.sh 先 seed 再起 uvicorn，否则 backfill 会报 "no such column"。
    from sqlalchemy import text

    with engine.begin() as conn:
        existing = {r[1] for r in conn.execute(text("PRAGMA table_info(task)")).fetchall()}
        if "main_task_id" not in existing:
            conn.execute(text("ALTER TABLE task ADD COLUMN main_task_id VARCHAR(32)"))
        # 主任务新增 责任人/责任部门/更新时间 字段，老库补 ALTER（与 main.py 启动期保持一致）
        mt_existing = {r[1] for r in conn.execute(text("PRAGMA table_info(main_task)")).fetchall()}
        if "owner_id" not in mt_existing:
            conn.execute(text("ALTER TABLE main_task ADD COLUMN owner_id VARCHAR(16)"))
        if "dept_id" not in mt_existing:
            conn.execute(text("ALTER TABLE main_task ADD COLUMN dept_id VARCHAR(16)"))
        if "updated_at" not in mt_existing:
            conn.execute(text("ALTER TABLE main_task ADD COLUMN updated_at TIMESTAMP"))
        # user.preferences：用户级偏好（行高等），老库补 ALTER，默认值 '{}'
        user_existing = {r[1] for r in conn.execute(text("PRAGMA table_info(\"user\")")).fetchall()}
        if "preferences" not in user_existing:
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN preferences TEXT NOT NULL DEFAULT '{}'"))

        # market_project.progress：本轮新增的项目进展冗余快照列，老库补 ALTER（默认空串）
        mp_existing = {r[1] for r in conn.execute(text("PRAGMA table_info(market_project)")).fetchall()}
        if "progress" not in mp_existing:
            conn.execute(text("ALTER TABLE market_project ADD COLUMN progress TEXT NOT NULL DEFAULT ''"))
    with SessionLocal() as db:
        created = seed(db, reset=reset)
    print(f"[seed] 完成（reset={reset}）: {created}")
    print("[seed] 演示账号初始密码见 deploy/.env.example 的 SEED_PASSWORD 说明")


if __name__ == "__main__":
    main()
