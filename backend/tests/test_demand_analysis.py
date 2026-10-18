"""车辆需求分析：车头按(车型×电池容量)组合、挂车按车型分行统计。"""
from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import MarketProject, ProjectTractorRequirement, ProjectTrailerRequirement


def _login(client, account="admin"):
    r = client.post("/api/v1/auth/login", json={"account": account, "password": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_demand_analysis_grouping(client, admin_headers):
    # 用市场部人员（郑凯/D01）作负责人，保证默认范围纳入；组合用唯一值避免与种子数据耦合
    PID = "MP_DA_TEST"
    with SessionLocal() as db:
        old = db.scalar(select(MarketProject).where(MarketProject.id == PID))
        if old:
            db.delete(old)
            db.commit()
        db.add(
            MarketProject(
                id=PID, name="DA测试项目", tractor_demand=10, trailer_demand=6,
                stage=50, owner="郑凯", created_by="U001",
            )
        )
        db.flush()
        db.add(ProjectTractorRequirement(project_id=PID, model="测试牵引车X", battery="测试电池Y", qty=4))
        db.add(ProjectTractorRequirement(project_id=PID, model="测试牵引车X", battery="测试电池Y", qty=6))
        db.add(ProjectTrailerRequirement(project_id=PID, model="测试挂车Z", qty=6))
        db.commit()

    r = client.get("/api/v1/dashboard/demand-analysis", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    # 车头：(测试牵引车X, 测试电池Y) 合计 10；预估消化 = 10 × 阶段50转化率（默认 0.5 → 5.0）
    tractor = body["tractor"]["all"]
    combo = next((x for x in tractor if x["model"] == "测试牵引车X" and x["battery"] == "测试电池Y"), None)
    assert combo is not None and combo["qty"] == 10
    assert abs(combo["digest"] - 5.0) < 1e-6

    # 挂车：测试挂车Z 总数量 6，预估消化 = 6 × 阶段50转化率（默认 0.5 → 3.0）
    trailer = body["trailer"]["all"]
    tr = next((x for x in trailer if x["model"] == "测试挂车Z"), None)
    assert tr is not None and tr["qty"] == 6
    assert abs(tr["digest"] - 3.0) < 1e-6

    # 阶段筛选：选 50 阶段（key "50"）应仅含该阶段组合，且数量正确
    by_stage = body["tractor"]["byStage"].get("50", [])
    combo2 = next((x for x in by_stage if x["model"] == "测试牵引车X" and x["battery"] == "测试电池Y"), None)
    assert combo2 is not None and combo2["qty"] == 10
    # 其它阶段不应出现该测试组合
    other = body["tractor"]["byStage"].get("10", [])
    assert not any(x["model"] == "测试牵引车X" for x in other)


def test_demand_analysis_churn_stage(client, admin_headers):
    """流失阶段：转化率 0%，计入总需求数但预估消化数为 0；车辆需求分析提供流失筛选标签。"""
    PID = "MP_DA_CHURN"
    with SessionLocal() as db:
        old = db.scalar(select(MarketProject).where(MarketProject.id == PID))
        if old:
            db.delete(old)
            db.commit()
        db.add(
            MarketProject(
                id=PID, name="流失测试项目", tractor_demand=8, trailer_demand=5,
                stage=0, owner="郑凯", created_by="U001",  # stage=0 即流失
            )
        )
        db.flush()
        db.add(ProjectTractorRequirement(project_id=PID, model="流失牵引车", battery="400度", qty=8))
        db.add(ProjectTrailerRequirement(project_id=PID, model="流失挂车", qty=5))
        db.commit()

    r = client.get("/api/v1/dashboard/demand-analysis", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    # 全量（全部）应含流失项目的需求：总需求计入，预估消化=0
    tractor = body["tractor"]["all"]
    churn_t = next((x for x in tractor if x["model"] == "流失牵引车" and x["battery"] == "400度"), None)
    assert churn_t is not None and churn_t["qty"] == 8
    assert abs(churn_t["digest"] - 0.0) < 1e-6

    trailer = body["trailer"]["all"]
    churn_tr = next((x for x in trailer if x["model"] == "流失挂车"), None)
    assert churn_tr is not None and churn_tr["qty"] == 5
    assert abs(churn_tr["digest"] - 0.0) < 1e-6

    # 按流失阶段筛选（key "0"）：仅显示流失项目，且数量正确
    by_churn_t = body["tractor"]["byStage"].get("0", [])
    assert any(x["model"] == "流失牵引车" and x["qty"] == 8 for x in by_churn_t)
    by_churn_tr = body["trailer"]["byStage"].get("0", [])
    assert any(x["model"] == "流失挂车" and x["qty"] == 5 for x in by_churn_tr)

    # 流失阶段不进入销售漏斗（漏斗仅取 MARKET_STAGES）
    funnel = client.get("/api/v1/dashboard/project-funnel", headers=admin_headers).json()
    assert all(s["stage"] != 0 for s in funnel["stages"])


def test_demand_analysis_digest_is_integer(client, admin_headers):
    """预估消化数量（digest）必须为整数：qty×转化率的小数按「四舍五入」取整。

    - qty=10 × 阶段25转化率(0.25) = 2.5 → 进为 3（验证 half-up，而非 banker's 2.5→2）
    - qty=10 × 阶段10转化率(0.10) = 1.0 → 整数 1
    """
    PID = "MP_DA_ROUND"
    with SessionLocal() as db:
        old = db.scalar(select(MarketProject).where(MarketProject.id == PID))
        if old:
            db.delete(old)
            db.commit()
        # 阶段 25 使转化率默认 0.25
        db.add(
            MarketProject(
                id=PID, name="取整测试", tractor_demand=20, trailer_demand=0,
                stage=25, owner="郑凯", created_by="U001",
            )
        )
        db.flush()
        db.add(ProjectTractorRequirement(project_id=PID, model="取整牵引车", battery="400度", qty=10))
        db.add(ProjectTractorRequirement(project_id=PID, model="取整牵引车2", battery="400度", qty=10))
        db.commit()

    body = client.get("/api/v1/dashboard/demand-analysis", headers=admin_headers).json()
    t = body["tractor"]["all"]
    # 两个组合各 10×0.25=2.5 → 3
    for m in ("取整牵引车", "取整牵引车2"):
        row = next((x for x in t if x["model"] == m), None)
        assert row is not None, f"缺少 {m}"
        assert row["digest"] == 3, f"{m} 预估消化应为 3，实际 {row['digest']}"
        assert isinstance(row["digest"], int), "digest 应为整数类型"


def test_demand_analysis_by_dept(client, admin_headers):
    # 部门筛选生效：指定一个二级部门应只返回该部门负责人名下项目需求
    full = client.get("/api/v1/dashboard/demand-analysis", headers=admin_headers).json()
    d12 = client.get("/api/v1/dashboard/demand-analysis?dept=D12", headers=admin_headers).json()

    full_tractor_units = sum(r["qty"] for r in full["tractor"]["all"])
    d12_tractor_units = sum(r["qty"] for r in d12["tractor"]["all"])
    # D12 是市场部二级部门之一，其数据量不应多于全量
    assert d12_tractor_units <= full_tractor_units
    # 阶段元信息一致（含流失阶段，置于最后；带转化率，供前端标签后缀）
    assert [s["stage"] for s in full["stages"]] == [10, 25, 50, 75, 90, 100, 0]
    assert all(0 <= s["prob"] <= 1 for s in full["stages"])
    # 流失阶段转化率固定 0%
    churn = next((s for s in full["stages"] if s["stage"] == 0), None)
    assert churn is not None and churn["label"] == "流失" and churn["prob"] == 0
