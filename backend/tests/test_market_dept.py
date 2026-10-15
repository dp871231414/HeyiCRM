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
    # 重新生成，确保数据干净且确定
    assert client.post("/api/v1/market-projects/reseed", headers=admin_headers).status_code == 200

    full = client.get("/api/v1/dashboard/project-funnel", headers=admin_headers).json()
    # 二级部门选项动态读取
    opts = {o["id"]: o["name"] for o in full["deptOptions"]}
    assert set(opts) == {"D12", "D13"}

    full_total = sum(s["count"] for s in full["stages"])
    # 全部 = 市场部子树全部人员
    d12 = client.get("/api/v1/dashboard/project-funnel?dept=D12", headers=admin_headers).json()
    d12_total = sum(s["count"] for s in d12["stages"])
    # 全部应大于任一单部门，且各二级部门数据互不重叠
    assert full_total > d12_total
    assert d12_total == sum(1 for _ in [o for o in client.get("/api/v1/meta/market-owners", headers=admin_headers).json() if o["deptId"] == "D12"])


def test_reseed_regenerates_from_market_personnel(client, admin_headers):
    r = client.post("/api/v1/market-projects/reseed", headers=admin_headers)
    assert r.status_code == 200
    created = r.json()["created"]

    owners = client.get("/api/v1/meta/market-owners", headers=admin_headers).json()
    # 每个市场部人员都应有 1 个项目
    assert created == len(owners)

    items = client.get("/api/v1/market-projects?size=500", headers=admin_headers).json()["items"]
    assert len(items) == created
    # 每个项目都带负责人直接部门
    assert all(it["ownerDeptId"] for it in items)
    # 负责人都在市场部人员清单内
    names = {o["name"] for o in owners}
    assert all(it["owner"] in names for it in items)
