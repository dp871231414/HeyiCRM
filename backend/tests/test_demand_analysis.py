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

    # 车头：(测试牵引车X, 测试电池Y) 合计 10
    tractor = body["tractor"]["all"]
    combo = next((x for x in tractor if x["model"] == "测试牵引车X" and x["battery"] == "测试电池Y"), None)
    assert combo is not None and combo["qty"] == 10

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


def test_demand_analysis_by_dept(client, admin_headers):
    # 部门筛选生效：指定一个二级部门应只返回该部门负责人名下项目需求
    full = client.get("/api/v1/dashboard/demand-analysis", headers=admin_headers).json()
    d12 = client.get("/api/v1/dashboard/demand-analysis?dept=D12", headers=admin_headers).json()

    full_tractor_units = sum(r["qty"] for r in full["tractor"]["all"])
    d12_tractor_units = sum(r["qty"] for r in d12["tractor"]["all"])
    # D12 是市场部二级部门之一，其数据量不应多于全量
    assert d12_tractor_units <= full_tractor_units
    # 阶段元信息一致（带转化率，供前端标签后缀）
    assert [s["stage"] for s in full["stages"]] == [10, 25, 50, 75, 90, 100]
    assert all(0 <= s["prob"] <= 1 for s in full["stages"])
