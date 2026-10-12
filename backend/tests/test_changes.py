"""本轮需求变更的回归测试。

覆盖：
1. 任务管理暴露「创建时间 / 更新时间」且只读；
2. 指标维护范围由权限决定，与角色属性（可见范围）解耦；
3. 统计周期支持范围内任意月份（不限于已有数据的月份）。
"""
from __future__ import annotations

import io

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


# ---------------------------------------------------------------- 模板与导出（本轮新增）

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _load_xlsx(content: bytes):
    from openpyxl import load_workbook

    return load_workbook(io.BytesIO(content))


def _header_of(ws, n: int, row: int) -> list:
    return [ws.cell(row=row, column=i).value for i in range(1, n + 1)]


def test_task_template_columns_match_list_and_form(client, admin_headers):
    """模板列名与「任务管理」列表/表单同一套叫法，且补齐了「数量单位」。"""
    from app.services.importer import HEADER_ROW, TASK_COLUMNS

    resp = client.get("/api/v1/tasks/import/template", headers=admin_headers)
    assert resp.status_code == 200
    ws = _load_xlsx(resp.content).worksheets[0]
    assert _header_of(ws, len(TASK_COLUMNS), HEADER_ROW) == TASK_COLUMNS
    # 不再使用「一级任务 / 二级任务」这类仅模板可见的旧叫法
    assert "一级任务" not in TASK_COLUMNS and "二级任务" not in TASK_COLUMNS
    # 表单里有、原来模板缺失的字段
    for name in ("任务名称", "任务分类", "任务描述", "数量单位"):
        assert name in TASK_COLUMNS


def test_task_template_styling(client, admin_headers):
    """说明栏 + 表头背景色 + 冻结表头。"""
    from app.services.importer import _BLUE_MAIN, HEADER_ROW, TASK_COLUMNS

    ws = _load_xlsx(client.get("/api/v1/tasks/import/template", headers=admin_headers).content).worksheets[0]
    banner = ws.cell(row=1, column=1).value
    assert banner and "模板" in str(banner), "顶部应有说明栏标题"
    head = ws.cell(row=HEADER_ROW, column=1)
    assert str(head.fill.fgColor.rgb).endswith(_BLUE_MAIN), "字段名称栏应有背景色"
    assert head.font.bold and ws.freeze_panes == f"A{HEADER_ROW + 1}"


def test_task_template_notes_mention_unit_and_system_columns(client, admin_headers):
    wb = _load_xlsx(client.get("/api/v1/tasks/import/template", headers=admin_headers).content)
    notes = wb["填写说明"]
    txt = " ".join(str(notes.cell(row=r, column=1).value or "") for r in range(1, notes.max_row + 1))
    assert "数量单位" in txt
    assert "创建人" in txt and "创建时间" in txt


def test_task_export_columns_align_with_list(client, admin_headers):
    """导出列 = 任务ID + 全部可填写列 + 系统列；业务列与导入模板同名。"""
    from app.services.importer import HEADER_ROW, TASK_COLUMNS, TASK_EXPORT_COLUMNS

    resp = client.get("/api/v1/tasks/export", headers=admin_headers)
    assert resp.status_code == 200
    ws = _load_xlsx(resp.content).worksheets[0]
    header = _header_of(ws, len(TASK_EXPORT_COLUMNS), HEADER_ROW)
    assert header == TASK_EXPORT_COLUMNS
    for name in TASK_COLUMNS:
        assert name in header
    for name in ("任务ID", "完成进度", "状态", "创建人", "创建时间", "更新时间"):
        assert name in header


def test_task_export_uses_dept_name_and_creator_name(client, admin_headers):
    """责任部门输出组织名称（不再是编码），创建人输出姓名。"""
    from app.services.importer import HEADER_ROW, TASK_EXPORT_COLUMNS

    ws = _load_xlsx(client.get("/api/v1/tasks/export", headers=admin_headers).content).worksheets[0]
    idx = {name: i + 1 for i, name in enumerate(TASK_EXPORT_COLUMNS)}
    depts, creators = set(), set()
    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        depts.add(ws.cell(row=r, column=idx["责任部门"]).value)
        creators.add(ws.cell(row=r, column=idx["创建人"]).value)
    assert "市场部" in depts, f"应为组织名称，实际：{depts}"
    assert not any(str(d).startswith("D0") for d in depts), "不应输出组织编码"
    assert any(c for c in creators), "创建人应有姓名"


def test_task_export_is_reimportable(client, admin_headers):
    """导出文件可直接当导入模板回灌（列齐全，能通过解析）。"""
    from app.services.importer import TASK_COLUMNS, TASK_OPTIONAL_COLUMNS, parse_rows

    content = client.get("/api/v1/tasks/export", headers=admin_headers).content
    rows = parse_rows(content, TASK_COLUMNS, 2000, optional=TASK_OPTIONAL_COLUMNS)
    assert rows, "导出内容应能被解析出数据行"
    assert all(r["任务名称"] for r in rows)


def test_parse_rows_skips_banner_row():
    """模板顶部有说明栏时，表头行应被自动定位。"""
    from openpyxl import Workbook

    from app.services.importer import TASK_COLUMNS, TASK_OPTIONAL_COLUMNS, parse_rows

    wb = Workbook()
    ws = wb.active
    ws.append(["重点任务导入标准模板"])
    ws.append(["请勿修改第 4 行字段名称"])
    ws.append([])
    ws.append(TASK_COLUMNS)
    vals = {
        "任务名称": "带说明栏的任务",
        "目标": 1,
        "已完成": 0,
        "计划开始日期": "2026-01-01",
        "计划结束日期": "2026-12-31",
        "责任部门": "市场部",
        "责任人": "郑凯",
    }
    ws.append([vals.get(c, "") for c in TASK_COLUMNS])
    buf = io.BytesIO()
    wb.save(buf)

    rows = parse_rows(buf.getvalue(), TASK_COLUMNS, 100, optional=TASK_OPTIONAL_COLUMNS)
    assert len(rows) == 1
    assert rows[0]["任务名称"] == "带说明栏的任务"


def test_parse_rows_tolerates_legacy_template_missing_optional_column():
    """老模板缺少「数量单位」等可选列时仍可导入，按空值处理。"""
    from openpyxl import Workbook

    from app.services.importer import TASK_COLUMNS, TASK_OPTIONAL_COLUMNS, parse_rows

    legacy = [c for c in TASK_COLUMNS if c != "数量单位"]
    wb = Workbook()
    ws = wb.active
    ws.append(legacy)
    vals = {
        "任务名称": "老模板任务",
        "目标": 1,
        "已完成": 0,
        "计划开始日期": "2026-01-01",
        "计划结束日期": "2026-12-31",
        "责任部门": "市场部",
        "责任人": "郑凯",
    }
    ws.append([vals.get(c, "") for c in legacy])
    buf = io.BytesIO()
    wb.save(buf)

    rows = parse_rows(buf.getvalue(), TASK_COLUMNS, 100, optional=TASK_OPTIONAL_COLUMNS)
    assert rows[0]["任务名称"] == "老模板任务"
    assert rows[0].get("数量单位", "") == ""


def test_parse_rows_still_rejects_missing_required_column():
    """必填列缺失仍需报错。"""
    from openpyxl import Workbook

    from app.services.importer import TASK_COLUMNS, TASK_OPTIONAL_COLUMNS, parse_rows

    cols = ["任务名称", "目标"]  # 缺少日期、部门、责任人等必填列
    wb = Workbook()
    ws = wb.active
    ws.append(cols)
    ws.append(["x", 1])
    buf = io.BytesIO()
    wb.save(buf)

    try:
        parse_rows(buf.getvalue(), TASK_COLUMNS, 100, optional=TASK_OPTIONAL_COLUMNS)
    except ValueError as exc:
        assert "模板缺少列" in str(exc)
    else:
        raise AssertionError("应抛出缺少列的 ValueError")


def test_task_list_exposes_creator_name(client, admin_headers):
    """列表返回创建人姓名，供新增的「创建人」列展示。"""
    items = client.get("/api/v1/tasks", headers=admin_headers).json()["items"]
    assert items
    for t in items:
        assert "createdById" in t and "createdByName" in t
    assert any(t["createdByName"] for t in items)


def test_template_has_no_blank_row_after_header(client, admin_headers):
    """表头下一行必须直接是示例行。

    回归：freeze_panes 若用 ws.cell(...) 会创建空单元格，导致数据整体下移一行、
    模板里多出一行空白（解析时虽能跳过，但肉眼可见地不整洁）。
    """
    from app.services.importer import HEADER_ROW, TASK_COLUMNS

    ws = _load_xlsx(client.get("/api/v1/tasks/import/template", headers=admin_headers).content).worksheets[0]
    assert ws.cell(row=HEADER_ROW, column=1).value == TASK_COLUMNS[0]
    assert ws.cell(row=HEADER_ROW + 1, column=1).value, "表头下一行应直接是示例行"
    assert ws.freeze_panes == f"A{HEADER_ROW + 1}"


def test_export_has_no_blank_row_after_header(client, admin_headers):
    from app.services.importer import HEADER_ROW

    ws = _load_xlsx(client.get("/api/v1/tasks/export", headers=admin_headers).content).worksheets[0]
    assert ws.cell(row=HEADER_ROW, column=1).value == "任务ID"
    assert ws.cell(row=HEADER_ROW + 1, column=1).value, "表头下一行应直接是数据"


# ---------------------------------------------------------------- 项目公司权限与删除（本轮新增）


def test_perm_catalog_exposes_project_actions(client, admin_headers):
    """权限目录暴露项目公司的增 / 改 / 删三个独立权限项，供角色按需勾选。"""
    catalog = client.get("/api/v1/permissions", headers=admin_headers).json()
    keys = {item["key"] for g in catalog["groups"] for item in g["items"]}
    assert {"project.create", "project.edit", "project.delete"} <= keys


def test_admin_role_includes_project_actions(client, admin_headers):
    roles = {r["id"]: r for r in client.get("/api/v1/roles", headers=admin_headers).json()}
    assert {"project.create", "project.edit", "project.delete"} <= set(roles["admin"]["permissions"])


def test_role_without_project_perm_cannot_manage_projects(client, admin_headers, head_headers):
    """部门负责人可维护项目公司指标（metric.edit_project），但没有项目公司管理权限。

    回归点：此前增删改的门是「具备公司整体目标权限且当前视角为全公司」，
    导致这类角色看得到数据却无法操作。现改为纯权限点判定。
    """
    denied_create = client.post(
        "/api/v1/projects", json={"name": "不应创建", "head": "x", "targets": []}, headers=head_headers
    )
    assert denied_create.status_code == 403
    assert client.patch("/api/v1/projects/PC1", json={"name": "不应改名", "head": "x"}, headers=head_headers).status_code == 403
    assert client.delete("/api/v1/projects/PC1", headers=head_headers).status_code == 403
    # 未被波及
    assert any(p["id"] == "PC1" for p in client.get("/api/v1/projects", headers=admin_headers).json())


def test_project_manage_configurable_via_custom_role(client, admin_headers):
    """给自定义角色勾上项目公司权限后即可操作——能力由权限决定，与角色标识无关。"""
    import time

    suffix = str(int(time.time() * 1000))[-6:]
    role = client.post(
        "/api/v1/roles",
        json={
            "name": f"项目管理员{suffix}",
            "description": "",
            "scope": "all",
            "permissions": ["metric.view", "project.create", "project.edit", "project.delete"],
        },
        headers=admin_headers,
    )
    assert role.status_code == 201, role.text
    rid = role.json()["id"]

    account = f"pm{suffix}"
    created_user = client.post(
        "/api/v1/users",
        json={
            "name": f"项目管理员{suffix}",
            "account": account,
            "password": "Demo#2026",
            "dept_id": "CO",
            "role_id": rid,
            "status": "active",
        },
        headers=admin_headers,
    )
    assert created_user.status_code == 201, created_user.text
    uid = created_user.json()["id"]

    try:
        headers, _ = login(client, account)
        made = client.post(
            "/api/v1/projects", json={"name": f"权限验证公司{suffix}", "head": "x", "targets": []}, headers=headers
        )
        assert made.status_code == 201, made.text
        pid = made.json()["data"]["id"]

        renamed = client.patch(f"/api/v1/projects/{pid}", json={"name": f"权限验证公司{suffix}b", "head": "y"}, headers=headers)
        assert renamed.status_code == 200, renamed.text
        assert client.delete(f"/api/v1/projects/{pid}", headers=headers).status_code == 200
    finally:
        client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
        client.delete(f"/api/v1/roles/{rid}", headers=admin_headers)


def test_project_delete_reassigns_dangling_refs(client, admin_headers):
    """删除项目公司：关联账号与子组织迁移到上级组织，不留悬空引用。

    回归点：此前只把账号置为停用、未改 dept_id，删除后 dept_id 会指向不存在的组织。
    """
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Organization, User

    made = client.post(
        "/api/v1/projects", json={"name": "待删除项目公司X", "head": "测试", "targets": []}, headers=admin_headers
    )
    assert made.status_code == 201, made.text
    pid = made.json()["data"]["id"]

    with SessionLocal() as db:
        db.add(Organization(id="DPX", name="待删除项目公司的子部门", type="dept", parent_id=pid, head="—", sort_order=900))
        db.add(
            User(
                id="U9X",
                name="临时账号X",
                account="tmpx",
                password_hash="x",
                dept_id=pid,
                role_id="member",
                status="active",
            )
        )
        db.commit()

    assert client.delete(f"/api/v1/projects/{pid}", headers=admin_headers).status_code == 200

    with SessionLocal() as db:
        assert db.get(Organization, pid) is None, "项目公司应已删除"
        child = db.get(Organization, "DPX")
        moved = db.get(User, "U9X")
        assert child is not None and child.parent_id == "CO", "子组织应上移到 CO，而非悬空"
        assert moved is not None and moved.dept_id == "CO", "账号归属应迁移到 CO"
        assert moved.status == "disabled", "账号应被停用而非删除"

        # 全库不应存在指向已删除组织的引用
        org_ids = {o.id for o in db.scalars(select(Organization)).all()}
        assert all(u.dept_id in org_ids for u in db.scalars(select(User)).all())
        assert all(o.parent_id is None or o.parent_id in org_ids for o in db.scalars(select(Organization)).all())

        # 清理临时数据
        if child is not None:
            db.delete(child)
        if moved is not None:
            db.delete(moved)
        db.commit()
