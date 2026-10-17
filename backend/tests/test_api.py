"""API 端到端测试 · 覆盖鉴权、权限、组织、账号、指标、任务、驾驶舱。"""
from __future__ import annotations

import io

from openpyxl import Workbook

from app.services.achievement import current_period
from tests.conftest import login


# ---------------------------------------------------------------- 鉴权


def test_login_success_and_me(client):
    headers, data = login(client, "admin")
    assert "account.role" in data["perms"]
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["user"]["name"] == "陈志明"


def test_login_wrong_password(client):
    resp = client.post("/api/v1/auth/login", json={"account": "admin", "password": "bad"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "账号或密码错误"


def test_login_unknown_account_same_message(client):
    resp = client.post("/api/v1/auth/login", json={"account": "nobody", "password": "bad"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "账号或密码错误"


def test_login_disabled_account(client):
    resp = client.post("/api/v1/auth/login", json={"account": "liming", "password": "123456"})
    assert resp.status_code == 403


def test_protected_without_token(client):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as fresh:
        assert fresh.get("/api/v1/dashboard/summary").status_code == 401


# ---------------------------------------------------------------- 权限与范围


def test_member_cannot_manage_accounts(client, member_headers):
    assert client.get("/api/v1/users", headers=member_headers).status_code == 403
    assert client.post("/api/v1/orgs", json={"name": "X", "parent_id": "CO"}, headers=member_headers).status_code == 403


def test_member_scope_self_tasks(client, member_headers):
    resp = client.get("/api/v1/tasks", headers=member_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    # 普通成员郑凯：仅本人相关任务
    assert items and all(t["owner"] == "郑凯" for t in items)


def test_admin_sees_more_tasks(client, admin_headers, member_headers):
    admin_total = client.get("/api/v1/tasks", headers=admin_headers).json()["total"]
    member_total = client.get("/api/v1/tasks", headers=member_headers).json()["total"]
    assert admin_total >= member_total


def test_metric_board_open_by_perm_not_scope(client, head_headers):
    """指标维护只按角色权限开放，不再按数据可见范围隔离（口径变更）。

    回归点：原先部门负责人访问项目公司 / 其他部门的看板会被拦成 403，
    并按可见范围裁剪项目公司列表。现按既定口径放开 —— 数据范围仅作用于任务模块。
    """
    resp = client.get("/api/v1/metrics/board", params={"org_id": "D06"}, headers=head_headers)
    assert resp.status_code == 200
    # 跨组织不再拦截：有 metric.view 即可查看任意组织
    assert client.get("/api/v1/metrics/board", params={"org_id": "PC1"}, headers=head_headers).status_code == 200
    assert client.get("/api/v1/metrics/board", params={"org_id": "D01"}, headers=head_headers).status_code == 200
    # 项目公司按全公司口径列出，不按可见范围裁剪
    assert len(resp.json()["project"]["companies"]) == 3


# ---------------------------------------------------------------- 组织


def test_org_tree_excludes_projects(client, admin_headers):
    orgs = client.get("/api/v1/orgs", headers=admin_headers).json()
    types = {o["type"] for o in orgs}
    assert "project" not in types
    assert any(o["name"] == "市场部" for o in orgs)


def test_create_and_delete_dept(client, admin_headers):
    created = client.post("/api/v1/orgs", json={"name": "测试部", "parent_id": "CO", "head": "张三"}, headers=admin_headers)
    assert created.status_code == 201
    oid = created.json()["id"]
    dup = client.post("/api/v1/orgs", json={"name": "测试部", "parent_id": "CO"}, headers=admin_headers)
    assert dup.status_code == 409
    deleted = client.delete(f"/api/v1/orgs/{oid}", headers=admin_headers)
    assert deleted.status_code == 200


def test_delete_market_dept_locked(client, admin_headers):
    # 系统默认市场部（D01）按 ID 锁定，无论是否有账号都不允许删除
    resp = client.delete("/api/v1/orgs/D01", headers=admin_headers)
    assert resp.status_code == 409
    assert "市场部" in resp.json()["detail"]


def test_delete_dept_with_users_blocked(client, admin_headers):
    # 其它部门（如 D02 资产部）有账号时仍按原规则拦截
    resp = client.delete("/api/v1/orgs/D02", headers=admin_headers)
    assert resp.status_code == 409
    assert "账号" in resp.json()["detail"]


def test_cannot_delete_company_root(client, admin_headers):
    assert client.delete("/api/v1/orgs/CO", headers=admin_headers).status_code == 409


# ---------------------------------------------------------------- 项目公司


def test_project_crud(client, admin_headers):
    period = current_period()
    created = client.post(
        "/api/v1/projects",
        json={"name": "合一测试运营公司", "head": "测试", "targets": [{"metric_id": "OP_REV", "value": 1000, "year": period[:4]}]},
        headers=admin_headers,
    )
    assert created.status_code == 201
    pid = created.json()["data"]["id"]

    listed = client.get("/api/v1/projects", headers=admin_headers).json()
    assert any(p["id"] == pid for p in listed)

    imp = client.get(f"/api/v1/projects/{pid}/impact", headers=admin_headers).json()
    assert imp["targets"] == 1

    updated = client.patch(f"/api/v1/projects/{pid}", json={"name": "合一测试运营公司2", "head": "测试2"}, headers=admin_headers)
    assert updated.status_code == 200

    deleted = client.delete(f"/api/v1/projects/{pid}", headers=admin_headers)
    assert deleted.status_code == 200
    # 连带清理目标值
    after = client.get("/api/v1/projects", headers=admin_headers).json()
    assert all(p["id"] != pid for p in after)


# ---------------------------------------------------------------- 角色与账号


def test_role_crud_and_constraints(client, admin_headers):
    created = client.post(
        "/api/v1/roles",
        json={"name": "数据查看员", "description": "只读", "scope": "all", "permissions": ["dashboard.view", "task.view"]},
        headers=admin_headers,
    )
    assert created.status_code == 201
    rid = created.json()["id"]

    dup = client.post("/api/v1/roles", json={"name": "数据查看员", "permissions": []}, headers=admin_headers)
    assert dup.status_code == 409

    # 删除内置角色被拒
    assert client.delete("/api/v1/roles/admin", headers=admin_headers).status_code == 409
    # 新建角色无关联账号，可删除
    assert client.delete(f"/api/v1/roles/{rid}", headers=admin_headers).status_code == 200


def test_role_delete_blocked_when_in_use(client, admin_headers):
    assert client.delete("/api/v1/roles/member", headers=admin_headers).status_code == 409


def test_permissions_catalog(client, admin_headers):
    data = client.get("/api/v1/permissions", headers=admin_headers).json()
    assert len(data["groups"]) == 7
    assert {g["menu"] for g in data["groups"]} == {
        "dashboard",
        "task",
        "metric",
        "market",
        "account",
        "system",
        "download",
    }
    assert {s["value"] for s in data["scopes"]} == {"self", "dept", "dept_sub", "all"}


def test_user_crud_and_scope_override(client, admin_headers):
    created = client.post(
        "/api/v1/users",
        json={"name": "测试员", "account": "testuser", "password": "Pass#2026", "dept_id": "D03", "role_id": "member", "scope": "dept", "status": "active"},
        headers=admin_headers,
    )
    assert created.status_code == 201
    uid = created.json()["id"]
    assert created.json()["effectiveScope"] == "dept"

    # 账号重复
    assert client.post(
        "/api/v1/users",
        json={"name": "测试员2", "account": "testuser", "password": "Pass#2026", "dept_id": "D03", "role_id": "member"},
        headers=admin_headers,
    ).status_code == 409

    # 新建时也必须显式选择范围：不传 scope → 422
    assert (
        client.post(
            "/api/v1/users",
            json={"name": "测试员3", "account": "testuser3", "password": "Pass#2026", "dept_id": "D03", "role_id": "member"},
            headers=admin_headers,
        ).status_code
        == 422
    )

    # 覆盖范围清空 → 同样拒绝（不再回退到角色默认）
    cleared = client.patch(
        f"/api/v1/users/{uid}",
        json={"name": "测试员", "dept_id": "D03", "role_id": "member", "scope": "", "status": "active"},
        headers=admin_headers,
    )
    assert cleared.status_code == 422

    # 显式改成另一档仍然生效
    updated = client.patch(
        f"/api/v1/users/{uid}",
        json={"name": "测试员", "dept_id": "D03", "role_id": "member", "scope": "dept_sub", "status": "active"},
        headers=admin_headers,
    )
    assert updated.status_code == 200 and updated.json()["effectiveScope"] == "dept_sub"

    # 停用
    st = client.post(f"/api/v1/users/{uid}/status", json={"status": "disabled"}, headers=admin_headers)
    assert st.status_code == 200 and st.json()["status"] == "disabled"
    # 新账号不可登录
    assert client.post("/api/v1/auth/login", json={"account": "testuser", "password": "Pass#2026"}).status_code == 403


# ---------------------------------------------------------------- 指标


def test_metric_board_three_modules(client, admin_headers):
    board = client.get("/api/v1/metrics/board", params={"org_id": "CO"}, headers=admin_headers).json()
    assert board["annual"] and board["monitor"] and board["project"]["companies"]
    sales = next(r for r in board["annual"] if r["metricId"] == "REV_SALE")
    # 年度目标 12000，10 月累计完成 9860 → 82.2%
    assert sales["target"] == 12000
    assert sales["actual"] == 9860
    assert abs(sales["rate"] - 0.8216) < 0.01
    assert sales["hasCollection"] is True
    assert sales["collLight"] in ("green", "amber", "red")


def test_dashboard_summary_matches_board(client, admin_headers):
    period = current_period()
    board = client.get("/api/v1/metrics/board", params={"period": period, "org_id": "CO"}, headers=admin_headers).json()
    summary = client.get("/api/v1/dashboard/summary", params={"period": period, "org_id": "CO"}, headers=admin_headers).json()
    assert summary["counts"]["total"] == len(board["annual"])
    assert "综合加权达成率" in summary["headline"]
    assert summary["timeProgress"] > 0


def test_metric_target_annual_period_rollup(client, admin_headers):
    """年度目标按年份存储：写入任意月度周期都落到年份周期。"""
    client.put(
        "/api/v1/metrics/targets",
        json={"metric_id": "REV_ENER", "org_id": "CO", "period": "2026-07", "value": 9000},
        headers=admin_headers,
    )
    board = client.get("/api/v1/metrics/board", params={"period": "2026-07", "org_id": "CO"}, headers=admin_headers).json()
    row = next(r for r in board["annual"] if r["metricId"] == "REV_ENER")
    assert row["target"] == 9000
    # 还原
    client.put(
        "/api/v1/metrics/targets",
        json={"metric_id": "REV_ENER", "org_id": "CO", "period": "2026", "value": 8600},
        headers=admin_headers,
    )


def test_metric_write_requires_perm_only(client, member_headers, admin_headers):
    # 普通成员无「维护公司整体目标」权限，写全公司指标被拒（只看权限，不看可见范围）
    resp = client.put(
        "/api/v1/metrics/actuals",
        json={"metric_id": "REV_SALE", "org_id": "CO", "period": current_period(), "value": 100},
        headers=member_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------- 任务


def test_task_progress_and_status(client, admin_headers):
    items = client.get("/api/v1/tasks", headers=admin_headers).json()["items"]
    t = next(i for i in items if i["id"] == "T202601")
    assert t["progress"] == 69
    assert t["statusLevel"] in ("normal", "overdue", "due_soon", "risk", "done")


def test_task_create_update_delete(client, admin_headers):
    payload = {
        "parent": "测试任务",
        "title": "子任务",
        "description": "desc",
        "abnormal": False,
        "target": 100,
        "done": 30,
        "unit": "%",
        "note": "首条进展",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "dept_id": "D03",
        "owner": "郑凯",
    }
    created = client.post("/api/v1/tasks", json=payload, headers=admin_headers)
    assert created.status_code == 201
    tid = created.json()["id"]
    assert created.json()["progress"] == 30

    bad = client.patch(f"/api/v1/tasks/{tid}", json={**payload, "end_date": "2020-01-01"}, headers=admin_headers)
    assert bad.status_code == 422

    assert client.delete(f"/api/v1/tasks/{tid}", headers=admin_headers).status_code == 200


def test_member_cannot_delete_task(client, member_headers):
    assert client.delete("/api/v1/tasks/T202601", headers=member_headers).status_code == 403


def test_dept_task_stats(client, admin_headers):
    stats = client.get("/api/v1/tasks/dept-stats", headers=admin_headers).json()
    assert stats and all("completion" in s for s in stats)
    total = sum(s["total"] for s in stats)
    assert total == client.get("/api/v1/tasks", headers=admin_headers).json()["total"]


# ---------------------------------------------------------------- 驾驶舱


def test_dashboard_overview(client, admin_headers):
    data = client.get("/api/v1/dashboard/overview", params={"org_id": "CO"}, headers=admin_headers).json()
    assert data["annual"] and data["monitor"] and data["projectCompare"]
    assert data["counts"]["total"] == len(data["annual"])


def test_dashboard_dept_task_stats(client, admin_headers):
    """部门任务完成度独立于总览取数，默认口径为全部。"""
    all_stats = client.get("/api/v1/dashboard/dept-task-stats", headers=admin_headers).json()
    assert all_stats and all("completion" in s for s in all_stats)
    assert sum(s["total"] for s in all_stats) == client.get("/api/v1/tasks", headers=admin_headers).json()["total"]


def test_metric_trend(client, admin_headers):
    trend = client.get("/api/v1/dashboard/metrics/REV_SALE/trend", params={"org_id": "CO"}, headers=admin_headers).json()
    assert len(trend["points"]) >= 7
    assert trend["points"][0]["period"].startswith("2026")


# ---------------------------------------------------------------- 导入


def _xlsx(rows, columns):
    wb = Workbook()
    ws = wb.active
    ws.append(columns)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _task_row(**kw) -> list:
    """按 TASK_COLUMNS 顺序构造一行，列名改动时用例自动跟随，不会因列序漂移而失效。"""
    from app.services.importer import TASK_COLUMNS

    return [kw.get(c, "") for c in TASK_COLUMNS]


def _task_sheet(rows: list[list]) -> tuple:
    from app.services.importer import TASK_COLUMNS

    return (
        "t.xlsx",
        _xlsx(rows, TASK_COLUMNS),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def test_task_import_with_errors(client, admin_headers):
    rows = [
        _task_row(任务名称="任务A", 任务分类="子A", 任务描述="描述", 任务进展="首条进展", 是否异常="否", 目标=100, 已完成=50,
                  计划开始日期="2026-01-01", 计划结束日期="2026-12-31", 责任部门="市场部", 责任人="郑凯"),
        # 任务名称为空 + 日期格式错 + 部门与人均不存在
        _task_row(任务分类="子B", 是否异常="否", 目标=100, 已完成=50,
                  计划开始日期="2026/01/01", 计划结束日期="2026-12-31", 责任部门="不存在部门", 责任人="不存在的人"),
    ]
    resp = client.post("/api/v1/tasks/import", files={"file": _task_sheet(rows)}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 0
    fields = {e["field"] for e in body["errors"]}
    assert {"任务名称", "计划开始日期", "责任部门", "责任人"} <= fields


def test_task_import_success(client, admin_headers):
    rows = [
        _task_row(任务名称="导入任务一", 任务分类="子任务一", 任务描述="市场部年度营收承接", 任务进展="首月进展正常", 是否异常="否", 目标=100, 已完成=50,
                  数量单位="万元", 计划开始日期="2026-01-01", 计划结束日期="2026-12-31",
                  责任部门="市场部", 责任人="郑凯"),
        _task_row(任务名称="导入任务一", 任务分类="子任务二", 任务描述="市场部专项任务", 任务进展="启动准备中", 是否异常="是", 目标=1, 已完成=0,
                  计划开始日期="2026-02-01", 计划结束日期="2026-12-31", 责任部门="市场部", 责任人="郑凯"),
    ]
    before = client.get("/api/v1/tasks", headers=admin_headers).json()["total"]
    resp = client.post("/api/v1/tasks/import", files={"file": _task_sheet(rows)}, headers=admin_headers)
    assert resp.status_code == 200 and resp.json()["imported"] == 2
    after = client.get("/api/v1/tasks", headers=admin_headers).json()["total"]
    assert after == before + 2
    # 「数量单位」必须真正写入（此前模板缺该列、导入代码又读错键名，单位一直为空）
    items = client.get("/api/v1/tasks", params={"keyword": "导入任务一"}, headers=admin_headers).json()["items"]
    assert {it["unit"] for it in items} == {"万元", ""}
    # 创建人由系统记录，等于导入操作者
    assert all(it["createdByName"] == "陈志明" for it in items)
    # 清理
    for it in items:
        client.delete(f"/api/v1/tasks/{it['id']}", headers=admin_headers)


def test_metric_import_period_mismatch(client, admin_headers):
    columns = ["指标编码", "指标名称", "统计周期", "统计组织", "实际值"]
    rows = [["REV_SALE", "销售收入", "1999-01", "CO", 100]]
    resp = client.post(
        "/api/v1/metrics/import",
        files={"file": ("m.xlsx", _xlsx(rows, columns), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 0
    assert any(e["field"] == "统计周期" for e in resp.json()["errors"])


def test_templates_downloadable(client, admin_headers):
    for url in ("/api/v1/tasks/import/template", "/api/v1/metrics/import/template"):
        resp = client.get(url, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.content[:2] == b"PK"  # xlsx 为 zip 容器


# ---------------------------------------------------------------------------
# 令牌解析健壮性：反代/网关可能重写 Authorization 头，Cookie 作为兜底
# ---------------------------------------------------------------------------
def test_auth_header_works(client):
    headers, _ = login(client, "admin")
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200


def test_overwritten_header_falls_back_to_cookie(client):
    """头被网关替换为无效令牌时，登录种下的 Cookie 应能兜底放行。"""
    login(client, "admin")  # 同时种下 HttpOnly Cookie
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer gateway-injected-junk"})
    assert resp.status_code == 200, resp.text


def test_invalid_token_without_cookie_rejected():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as fresh:
        resp = fresh.get("/api/v1/auth/me", headers={"Authorization": "Bearer gateway-injected-junk"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 指标维护授权口径（对齐原型 metricEditScope）
# ---------------------------------------------------------------------------
def test_board_edit_scope_admin_at_company(client, admin_headers):
    d = client.get("/api/v1/metrics/board", params={"org_id": "CO"}, headers=admin_headers).json()
    assert d["canEditAll"] is True
    assert set(d["editableProjects"]) == {"PC1", "PC2", "PC3"}


def test_board_edit_scope_admin_at_project(client, admin_headers):
    d = client.get("/api/v1/metrics/board", params={"org_id": "PC1"}, headers=admin_headers).json()
    # 项目视角下不开放公司整体目标编辑（否则会写出项目维度的公司级目标）
    assert d["canEditAll"] is False
    # 但全公司范围仍可维护全部项目公司
    assert set(d["editableProjects"]) == {"PC1", "PC2", "PC3"}


def test_board_project_edit_is_perm_based(client, head_headers, member_headers):
    """项目公司能否维护只看权限点，与数据可见范围无关。

    部门负责人（scope=dept_sub）持有 metric.edit_project，可维护全部项目公司；
    普通成员（scope=self）无该权限，仍为空。
    """
    head = client.get("/api/v1/metrics/board", params={"org_id": "D06"}, headers=head_headers).json()
    # D06 不是公司层级，不开放公司整体目标编辑
    assert head["canEditAll"] is False
    # 有 metric.edit_project 即可维护全部项目公司（不再受可见范围限制）
    assert set(head["editableProjects"]) == {"PC1", "PC2", "PC3"}

    member = client.get("/api/v1/metrics/board", params={"org_id": "CO"}, headers=member_headers).json()
    assert member["editableProjects"] == [], "无 project 权限时不应可维护"


def test_board_project_head_edit_covers_all_projects(client, project_headers):
    """项目公司负责人持 metric.edit_project，可维护全部项目公司（不再限定自家）。"""
    d = client.get("/api/v1/metrics/board", params={"org_id": "PC1"}, headers=project_headers).json()
    assert d["canEditAll"] is False
    assert set(d["editableProjects"]) == {"PC1", "PC2", "PC3"}


def test_board_org_type_exposed(client, admin_headers):
    d = client.get("/api/v1/metrics/board", params={"org_id": "D06"}, headers=admin_headers).json()
    assert d["orgType"] == "dept"
    assert d["orgId"] == "D06"


# ---------------------------------------------------------------------------
# 任务接口请求体契约（snake_case，见 docs/design.md §6.5）
# ---------------------------------------------------------------------------
def test_task_create_and_update_contract(client, admin_headers):
    body = {
        "parent": "契约验证任务",
        "title": "分类A",
        "description": "",
        "abnormal": False,
        "target": 4,
        "done": 1,
        "unit": "项",
        "note": "首条进展",
        "start_date": "2026-10-01",
        "end_date": "2026-12-31",
        "dept_id": "D03",
        "owner": "吴敏",
    }
    created = client.post("/api/v1/tasks", json=body, headers=admin_headers)
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    assert created.json()["startDate"] == "2026-10-01"
    assert created.json()["deptId"] == "D03"

    upd = client.patch(f"/api/v1/tasks/{tid}", json={**body, "done": 4}, headers=admin_headers)
    assert upd.status_code == 200, upd.text
    assert upd.json()["progress"] == 100

    assert client.delete(f"/api/v1/tasks/{tid}", headers=admin_headers).status_code == 200


def test_task_create_missing_fields_returns_422_detail(client, admin_headers):
    # 缺少 snake_case 必填字段时应返回 422 且 detail 为可读的数组
    resp = client.post("/api/v1/tasks", json={"parent": "缺字段"}, headers=admin_headers)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list) and detail
    assert all("msg" in e for e in detail)
