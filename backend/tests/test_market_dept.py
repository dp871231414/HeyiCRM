"""市场部锁定、二级部门筛选、负责人范围与项目重新生成。"""
from __future__ import annotations

from app.constants import DEFAULT_MARKET_DEPT_ID


def _login(client, account="admin"):
    r = client.post("/api/v1/auth/login", json={"account": account, "password": "123456"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_market_dept_locked(client, admin_headers):
    # 系统默认市场部按 ID 锁定，不可删除
    assert client.delete(f"/api/v1/orgs/{DEFAULT_MARKET_DEPT_ID}", headers=admin_headers).status_code == 409
    # 名称仍可改
    r = client.patch(
        f"/api/v1/orgs/{DEFAULT_MARKET_DEPT_ID}",
        json={"name": "市场部（默认）", "head": "林雪"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    # 还原名称，避免影响其它测试
    client.patch(
        f"/api/v1/orgs/{DEFAULT_MARKET_DEPT_ID}",
        json={"name": "市场部", "head": "林雪"},
        headers=admin_headers,
    )


def test_market_sub_departments_exist(client, admin_headers):
    orgs = {o["id"]: o for o in client.get("/api/v1/orgs", headers=admin_headers).json()}
    assert DEFAULT_MARKET_DEPT_ID in orgs
    # 市场部下应有两个二级部门（市场1部 / 市场2部）
    subs = [o for o in orgs.values() if o["parentId"] == DEFAULT_MARKET_DEPT_ID]
    assert {o["name"] for o in subs} == {"市场1部", "市场2部"}


def test_market_owners_only_market_tree(client, admin_headers):
    owners = client.get("/api/v1/meta/market-owners", headers=admin_headers).json()
    # 返回的都应归属市场部子树（D01 / D12 / D13）
    assert all(o["deptId"] in (DEFAULT_MARKET_DEPT_ID, "D12", "D13") for o in owners)
    # 非市场部人员不应出现（如资产部赵国强）
    assert not any(o["name"] == "赵国强" for o in owners)
    # 每条都带直接所属部门
    assert all(o["deptName"] for o in owners)


def test_funnel_dept_filter(client, admin_headers):
    # 漏斗按二级部门筛选（种子数据已含市场项目，无需重新生成）
    full = client.get("/api/v1/dashboard/project-funnel", headers=admin_headers).json()
    # 二级部门选项动态读取
    opts = {o["id"]: o["name"] for o in full["deptOptions"]}
    assert set(opts) == {"D12", "D13"}

    full_total = sum(s["count"] for s in full["stages"])
    # 种子数据应已有项目
    assert full_total > 0
    # 单部门漏斗数量应不超过全量（各二级部门数据互不重叠）
    d12 = client.get("/api/v1/dashboard/project-funnel?dept=D12", headers=admin_headers).json()
    d12_total = sum(s["count"] for s in d12["stages"])
    assert d12_total <= full_total
