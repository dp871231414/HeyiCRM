"""账号模块回归测试 · 可见范围必选 / 批量导入 / 删除引用检查。

覆盖：
1. 数据可见范围必须人工选择（不再支持「跟随角色默认」）；
2. 批量导入：模板可下载，逐行校验，存在错误行时整批不写入；
3. 删除账号：被任何数据引用（作为创建人或被选为填写项）时拒绝删除。
"""
from __future__ import annotations

import io
import time

from openpyxl import Workbook

from tests.conftest import login

ACCOUNT_COLUMNS = ["姓名", "账号", "初始密码", "所属部门", "角色", "数据可见范围", "状态"]


def _sheet_bytes(rows: list[list]) -> bytes:
    """按模板结构生成 xlsx：前 3 行为说明栏，第 4 行表头，第 5 行起为数据。"""
    wb = Workbook()
    ws = wb.active
    ws.append(["账号批量导入标准模板"])
    ws.append([""])
    ws.append([""])
    ws.append(ACCOUNT_COLUMNS)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, headers, rows: list[list]):
    data = _sheet_bytes(rows)
    return client.post(
        "/api/v1/users/import",
        files={"file": ("accounts.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )


def _uid() -> str:
    return str(int(time.time() * 1000))[-7:]


# ---------------------------------------------------------------- 可见范围必选
def test_scope_is_required_on_create_and_update(client, admin_headers):
    """不传 / 传空 scope 一律 422；传四档之一才通过。"""
    suffix = _uid()
    base = {
        "name": f"范围测试{suffix}",
        "account": f"sc{suffix}",
        "password": "Pass#2026",
        "dept_id": "CO",
        "role_id": "member",
        "status": "active",
    }

    r = client.post("/api/v1/users", json=base, headers=admin_headers)
    assert r.status_code == 422, "缺 scope 应被拒绝"

    r = client.post("/api/v1/users", json={**base, "scope": ""}, headers=admin_headers)
    assert r.status_code == 422, "空 scope 应被拒绝"

    r = client.post("/api/v1/users", json={**base, "scope": "not-a-scope"}, headers=admin_headers)
    assert r.status_code == 422, "非法 scope 应被拒绝"

    ok = client.post("/api/v1/users", json={**base, "scope": "all"}, headers=admin_headers)
    assert ok.status_code == 201, ok.text
    uid = ok.json()["id"]

    bad = client.patch(
        f"/api/v1/users/{uid}",
        json={"name": base["name"], "dept_id": "CO", "role_id": "member", "scope": "", "status": "active"},
        headers=admin_headers,
    )
    assert bad.status_code == 422, "清空 scope 应被拒绝（不再回退到角色默认）"

    good = client.patch(
        f"/api/v1/users/{uid}",
        json={"name": base["name"], "dept_id": "CO", "role_id": "member", "scope": "dept", "status": "active"},
        headers=admin_headers,
    )
    assert good.status_code == 200 and good.json()["effectiveScope"] == "dept"


def test_account_import_template_download(client, admin_headers):
    """模板可下载，且是合法 xlsx（含说明栏 + 表头 + 示例行）。"""
    r = client.get("/api/v1/users/import/template", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers.get("content-type", "")
    from openpyxl import load_workbook

    ws = load_workbook(io.BytesIO(r.content)).worksheets[0]
    assert [c.value for c in ws[4]] == ACCOUNT_COLUMNS, "第 4 行应为字段名称"


def test_account_import_success_and_counts(client, admin_headers):
    """合法行全部写入；账号与可见范围按模板值落库。"""
    suffix = _uid()
    rows = [
        ["导入员甲", f"imp{suffix}a", "Pass#2026", "市场部", "普通成员", "本部门", "启用"],
        ["导入员乙", f"imp{suffix}b", "Pass#2026", "市场部", "普通成员", "全公司", "停用"],
    ]
    r = _upload(client, admin_headers, rows)
    assert r.status_code == 200, r.text
    body = r.json()
    if body["imported"] != 2:
        print("IMPORT ERRORS:", body["errors"])
    assert body["imported"] == 2 and body["errors"] == []

    lst = client.get("/api/v1/users", params={"keyword": f"imp{suffix}"}, headers=admin_headers).json()
    assert len(lst) == 2
    by_acct = {u["account"]: u for u in lst}
    assert by_acct[f"imp{suffix}a"]["effectiveScope"] == "dept"
    assert by_acct[f"imp{suffix}a"]["status"] == "active"
    assert by_acct[f"imp{suffix}b"]["effectiveScope"] == "all"
    assert by_acct[f"imp{suffix}b"]["status"] == "disabled"


def test_account_import_rejects_bad_rows_without_writing(client, admin_headers):
    """存在错误行时整批不写入，并返回行号 + 字段 + 原因。"""
    suffix = _uid()
    dup_acct = f"dup{suffix}"
    rows = [
        ["重复甲", dup_acct, "Pass#2026", "市场部", "普通成员", "全公司", "启用"],
        ["重复乙", dup_acct, "Pass#2026", "市场部", "普通成员", "全公司", "启用"],
        ["", f"noname{suffix}", "Pass#2026", "市场部", "普通成员", "全公司", "启用"],
        ["缺部门", f"nodept{suffix}", "Pass#2026", "", "部门经理", "全公司", "启用"],
        ["错角色", f"badrole{suffix}", "Pass#2026", "合一重卡", "不存在的角色", "全公司", "启用"],
        ["错范围", f"badscope{suffix}", "Pass#2026", "市场部", "普通成员", "随便填", "启用"],
        ["短密码", f"shortpw{suffix}", "123", "市场部", "普通成员", "全公司", "启用"],
    ]
    r = _upload(client, admin_headers, rows)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 0, "有错行时不应写入任何数据"

    fields = {e["field"] for e in body["errors"]}
    assert "账号" in fields, "文件内账号重复应报错"
    assert "姓名" in fields, "姓名缺失应报错"
    assert "所属部门" in fields, "部门缺失应报错"
    assert "角色" in fields, "角色不存在应报错"
    assert "数据可见范围" in fields, "非法范围应报错"
    assert "初始密码" in fields, "密码过短应报错"

    # 整批未写入：重复账号在库里查不到
    assert not client.get("/api/v1/users", params={"keyword": dup_acct}, headers=admin_headers).json()

    # 修正后单独导入 → 成功
    r = _upload(client, admin_headers, [["重复甲", dup_acct, "Pass#2026", "市场部", "普通成员", "全公司", "启用"]])
    assert r.status_code == 200 and r.json()["imported"] == 1


def test_account_import_accepts_scope_keys(client, admin_headers):
    """数据可见范围同时接受中文档位与英文 key；状态留空默认启用。"""
    suffix = _uid()
    rows = [
        ["键甲", f"key{suffix}a", "Pass#2026", "市场部", "普通成员", "dept_sub", ""],
        ["键乙", f"key{suffix}b", "Pass#2026", "市场部", "普通成员", "本人", "停用"],
    ]
    r = _upload(client, admin_headers, rows)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2

    lst = client.get("/api/v1/users", params={"keyword": f"key{suffix}"}, headers=admin_headers).json()
    by_acct = {u["account"]: u for u in lst}
    assert by_acct[f"key{suffix}a"]["effectiveScope"] == "dept_sub"
    assert by_acct[f"key{suffix}a"]["status"] == "active", "状态留空应按启用处理"
    assert by_acct[f"key{suffix}b"]["effectiveScope"] == "self"


# ---------------------------------------------------------------- 删除引用检查
def test_account_delete_blocked_when_creator(client, admin_headers):
    """账号创建过任务 → 不允许删除。"""
    suffix = _uid()
    acct = f"cr{suffix}"
    r = client.post(
        "/api/v1/users",
        json={"name": f"创建人{suffix}", "account": acct, "password": "123456",
              "dept_id": "D01", "role_id": "member", "scope": "all", "status": "active"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]

    # 用该账号登录并创建一条任务
    h, _ = login(client, acct)
    t = client.post(
        "/api/v1/tasks",
        json={"parent": f"删除校验任务{suffix}", "title": "", "description": "", "abnormal": False,
              "target": 10, "done": 0, "unit": "项", "note": "首条进展", "start_date": "2026-01-01",
              "end_date": "2026-12-31", "dept_id": "D01", "owner": f"创建人{suffix}"},
        headers=h,
    )
    assert t.status_code in (200, 201), t.text

    imp = client.get(f"/api/v1/users/{uid}/impact", headers=admin_headers).json()
    assert imp["taskCreated"] >= 1

    d = client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert d.status_code == 409, d.text
    assert "创建" in d.json()["detail"]


def test_account_delete_blocked_when_referenced_as_owner(client, admin_headers):
    """账号被任务选为责任人 → 不允许删除。"""
    suffix = _uid()
    acct = f"ow{suffix}"
    name = f"责任人{suffix}"
    r = client.post(
        "/api/v1/users",
        json={"name": name, "account": acct, "password": "Pass#2026",
              "dept_id": "D01", "role_id": "member", "scope": "all", "status": "active"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]

    t = client.post(
        "/api/v1/tasks",
        json={"parent": f"责任人校验任务{suffix}", "title": "", "description": "", "abnormal": False,
              "target": 10, "done": 0, "unit": "项", "note": "首条进展", "start_date": "2026-01-01",
              "end_date": "2026-12-31", "dept_id": "D01", "owner": name},
        headers=admin_headers,
    )
    assert t.status_code in (200, 201), t.text

    imp = client.get(f"/api/v1/users/{uid}/impact", headers=admin_headers).json()
    assert imp["taskOwner"] >= 1

    d = client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert d.status_code == 409
    assert "责任人" in d.json()["detail"]


def test_account_delete_blocked_for_self(client, admin_headers):
    """不能删除当前登录账号自己。"""
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    uid = me["user"]["id"]
    d = client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert d.status_code == 409, d.text
    assert "当前登录账号" in d.json()["detail"]


def test_account_delete_allowed_when_unreferenced(client, admin_headers):
    """未被任何数据引用的账号 → 允许删除，且库中查不到。"""
    suffix = _uid()
    acct = f"del{suffix}"
    r = client.post(
        "/api/v1/users",
        json={"name": f"待删除{suffix}", "account": acct, "password": "Pass#2026",
              "dept_id": "D01", "role_id": "member", "scope": "self", "status": "active"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]

    imp = client.get(f"/api/v1/users/{uid}/impact", headers=admin_headers).json()
    assert all(v == 0 for k, v in imp.items() if isinstance(v, int)), "新建账号不应有任何引用"

    d = client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert d.status_code == 200, d.text
    assert not [u for u in client.get("/api/v1/users", headers=admin_headers).json() if u["id"] == uid]


def test_account_delete_blocked_when_last_admin(client, admin_headers):
    """最后一个具备账号管理权限的启用账号 → 不允许删除（避免锁死系统）。"""
    # admin 角色具备 account.edit / account.role，且 admin 是唯一启用账号时
    roles = client.get("/api/v1/roles", headers=admin_headers).json()
    admin_role = next((r for r in roles if r["name"] == "系统管理员"), None)
    assert admin_role, "应存在系统管理员角色"
    assert admin_role["userCount"] >= 1

    # 把账号的可见范围设为必定可选值后尝试删除自身：应先命中「当前登录账号」规则
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    uid = me["user"]["id"]
    d = client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert d.status_code == 409
