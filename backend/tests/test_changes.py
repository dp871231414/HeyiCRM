"""本轮需求变更的回归测试。

覆盖：
1. 任务管理暴露「创建时间 / 更新时间」且只读；
2. 指标维护范围由权限决定，与角色属性（可见范围）解耦；
3. 统计周期支持范围内任意月份（不限于已有数据的月份）。
"""
from __future__ import annotations

from tests.conftest import login


def _task_body(dept_id: str = "D01", owner: str = "林雪") -> dict:
    return {
        "parent": "变更测试任务",
        "title": "二级分类",
        "description": "",
        "abnormal": False,
        "target": 100,
        "done": 0,
        "unit": "万元",
        "note": "",
        "start_date": "2026-10-01",
        "end_date": "2026-12-31",
        "dept_id": dept_id,
        "owner": owner,
    }


# ---------------------------------------------------------------- 任务时间字段


def test_task_list_exposes_timestamps(client, admin_headers):
    """列表返回 createdAt / updatedAt，供前端只读展示。"""
    items = client.get("/api/v1/tasks", headers=admin_headers).json()["items"]
    assert items, "种子数据应含任务"
    for t in items:
        assert "createdAt" in t and "updatedAt" in t
        assert t["createdAt"], "创建时间不应为空（系统自动记录）"


def test_task_update_touches_updated_at(client, admin_headers):
    created = client.post("/api/v1/tasks", json=_task_body(), headers=admin_headers).json()
    before = created["updatedAt"]
    assert before

    body = _task_body()
    body["done"] = 60
    updated = client.patch(f"/api/v1/tasks/{created['id']}", json=body, headers=admin_headers).json()
    assert updated["done"] == 60
    assert updated["updatedAt"] >= before
    # 创建时间不被修改
    assert updated["createdAt"] == created["createdAt"]

    client.delete(f"/api/v1/tasks/{created['id']}", headers=admin_headers)


def test_task_timestamps_not_writable_by_client(client, admin_headers):
    """请求体里塞时间字段应被忽略（只读，由系统记录）。"""
    body = _task_body()
    body["createdAt"] = "1999-01-01T00:00:00+00:00"
    body["updatedAt"] = "1999-01-01T00:00:00+00:00"
    created = client.post("/api/v1/tasks", json=body, headers=admin_headers).json()
    assert not created["createdAt"].startswith("1999")
    client.delete(f"/api/v1/tasks/{created['id']}", headers=admin_headers)


# ---------------------------------------------------------------- 权限可配置


def test_permissions_catalog_exposes_new_metric_keys(client, admin_headers):
    groups = client.get("/api/v1/permissions", headers=admin_headers).json()["groups"]
    metric = next(g for g in groups if g["menu"] == "metric")
    keys = {i["key"] for i in metric["items"]}
    assert {"metric.edit", "metric.edit_company", "metric.edit_project"} <= keys


def test_board_reports_edit_perms(client, admin_headers):
    d = client.get("/api/v1/metrics/board", params={"org_id": "CO"}, headers=admin_headers).json()
    assert d["perms"] == {"edit": True, "editCompany": True, "editProject": True}


def test_company_edit_gated_by_permission_not_scope(client, admin_headers):
    """仅去掉 metric.edit_company 后，即使可见范围仍是「全公司」也不能维护公司整体目标。

    这条断言正是本次改造的核心：操作门槛只看权限，不看角色属性。
    """
    from app.db.session import SessionLocal
    from app.models import Role

    with SessionLocal() as db:
        role = db.get(Role, "admin")
        original = list(role.permissions or [])
        scope_before = role.scope
        role.permissions = [p for p in original if p != "metric.edit_company"]
        db.commit()
        try:
            d = client.get("/api/v1/metrics/board", params={"org_id": "CO"}, headers=admin_headers).json()
            assert d["perms"]["edit"] is True
            assert d["perms"]["editCompany"] is False
            # 可见范围未变（仍为全公司），但编辑权已被权限收回
            assert d["canEditAll"] is False
        finally:
            role.permissions = original
            role.scope = scope_before
            db.commit()


def test_project_edit_gated_by_permission(client, admin_headers):
    from app.db.session import SessionLocal
    from app.models import Role

    with SessionLocal() as db:
        role = db.get(Role, "admin")
        original = list(role.permissions or [])
        role.permissions = [p for p in original if p != "metric.edit_project"]
        db.commit()
        try:
            d = client.get("/api/v1/metrics/board", params={"org_id": "CO"}, headers=admin_headers).json()
            assert d["editableProjects"] == []
        finally:
            role.permissions = original
            db.commit()


def test_dept_head_cannot_edit_company_targets(client, head_headers):
    """部门负责人无 metric.edit_company，公司整体目标只读。"""
    d = client.get("/api/v1/metrics/board", params={"org_id": "D06"}, headers=head_headers).json()
    assert d["canEditAll"] is False
    assert d["perms"]["editCompany"] is False


def test_role_is_system_is_configurable(client, admin_headers):
    """内置标记可配置：新建角色可设为内置，且可再取消。"""
    payload = {
        "name": "可配置内置角色-测试",
        "description": "",
        "scope": "self",
        "permissions": ["dashboard.view"],
        "isSystem": True,
    }
    created = client.post("/api/v1/roles", json=payload, headers=admin_headers).json()
    assert created["isSystem"] is True

    # 内置状态下不可删除
    blocked = client.delete(f"/api/v1/roles/{created['id']}", headers=admin_headers)
    assert blocked.status_code == 409

    # 取消内置后即可删除
    off = dict(payload, name="可配置内置角色-测试", isSystem=False)
    assert client.patch(f"/api/v1/roles/{created['id']}", json=off, headers=admin_headers).json()["isSystem"] is False
    assert client.delete(f"/api/v1/roles/{created['id']}", headers=admin_headers).status_code == 200


def test_role_update_without_is_system_keeps_value(client, admin_headers):
    """未携带 isSystem 时保持原值，避免被误清空。"""
    roles = client.get("/api/v1/roles", headers=admin_headers).json()
    admin = next(r for r in roles if r["id"] == "admin")
    assert admin["isSystem"] is True

    payload = {
        "name": admin["name"],
        "description": admin["description"],
        "scope": admin["scope"],
        "permissions": admin["permissions"],
    }
    updated = client.patch("/api/v1/roles/admin", json=payload, headers=admin_headers).json()
    assert updated["isSystem"] is True


# ---------------------------------------------------------------- 周期范围


def test_board_accepts_month_without_data(client, admin_headers):
    """统计周期可选范围内任意月份，无数据也应正常返回而非报错。"""
    for period in ("2026-09", "2099-12"):
        resp = client.get(
            "/api/v1/metrics/board", params={"org_id": "CO", "period": period}, headers=admin_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["period"] == period
