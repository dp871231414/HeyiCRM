"""文档中心接口测试：列表 / 获取 / 编辑 / 分组 / 两级权限 / 新建 / 同步。"""
from __future__ import annotations

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User

BUILTIN_KEYS = {"usage", "prd", "tech", "test", "visual", "skill", "devnotes"}


def test_list_docs(client, admin_headers):
    """文档中心包含 7 类文档，每条带渲染后的 html 与分组字段。"""
    r = client.get("/api/v1/system/docs", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    keys = {d["key"] for d in data}
    assert BUILTIN_KEYS <= keys
    assert all("html" in d and "group" in d for d in data)
    by_key = {d["key"]: d for d in data}
    # 使用说明面向终端用户→用户文档；其余为开发文档
    assert by_key["usage"]["group"] == "用户文档"
    assert by_key["prd"]["group"] == "开发文档"


def test_get_doc_and_404(client, admin_headers):
    r = client.get("/api/v1/system/docs/prd", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["key"] == "prd"

    r = client.get("/api/v1/system/docs/not_exist", headers=admin_headers)
    assert r.status_code == 404

    # 设计文档已合并入技术文档，应不再独立存在
    r = client.get("/api/v1/system/docs/design", headers=admin_headers)
    assert r.status_code == 404


def test_update_markdown_renders_html(client, admin_headers):
    """编辑 markdown 文档后，获取应返回转译后的 HTML（标题/段落标签）。"""
    body = "# 标题一\n\n这是正文段落。"
    r = client.put(
        "/api/v1/system/docs/prd",
        json={"content": body, "fmt": "markdown"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    v1 = r.json()["version"]

    got = client.get("/api/v1/system/docs/prd", headers=admin_headers).json()
    assert got["version"] == v1
    assert "<h1" in got["html"] and "这是正文段落" in got["html"]


def test_update_html_keeps_raw(client, admin_headers):
    """html 格式文档原样返回（前端用 iframe srcdoc 渲染）。"""
    r = client.put(
        "/api/v1/system/docs/usage",
        json={"content": "<b>富文本内容</b>", "fmt": "html"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    got = client.get("/api/v1/system/docs/usage", headers=admin_headers).json()
    assert got["html"] == "<b>富文本内容</b>"


def test_update_group_keeps_key_and_title(client, admin_headers):
    """改分组/标题不改变 doc_key，且分组变更不触发版本号 +1（仅 content 变更才 +1）。"""
    before = client.get("/api/v1/system/docs/prd", headers=admin_headers).json()
    r = client.put(
        "/api/v1/system/docs/prd",
        json={"title": "产品需求文档（改名测试）", "group": "用户文档"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    after = r.json()
    assert after["key"] == "prd"  # doc_key 不变
    assert after["title"] == "产品需求文档（改名测试）"
    assert after["group"] == "用户文档"
    assert after["version"] == before["version"]  # 未改动 content，版本号不变
    # 还原
    client.put(
        "/api/v1/system/docs/prd",
        json={"title": "产品需求文档", "group": "开发文档"},
        headers=admin_headers,
    )


def test_create_doc_auto_and_explicit_key(client, admin_headers):
    """新建文档：省略 key 时后端自动生成；显式 key 须符合规则；重复 / 非法 key 报错。"""
    # 自动生成 key
    r1 = client.post(
        "/api/v1/system/docs",
        json={"title": "临时公告", "content": "hello", "group": "默认文档"},
        headers=admin_headers,
    )
    assert r1.status_code == 201
    created = r1.json()
    assert created["key"].startswith("doc_")
    assert created["group"] == "默认文档"

    # 显式 key
    r2 = client.post(
        "/api/v1/system/docs",
        json={"key": "notice_01", "title": "公告一", "group": "用户文档"},
        headers=admin_headers,
    )
    assert r2.status_code == 201
    assert r2.json()["key"] == "notice_01"

    # 重复 key -> 409
    r3 = client.post(
        "/api/v1/system/docs",
        json={"key": "notice_01", "title": "重复"},
        headers=admin_headers,
    )
    assert r3.status_code == 409

    # 非法 key -> 422（Pydantic 字段校验）
    r4 = client.post(
        "/api/v1/system/docs",
        json={"key": "Bad Key!", "title": "非法"},
        headers=admin_headers,
    )
    assert r4.status_code == 422

    # 清理新建文档（无删除接口，直接落库清理测试数据）
    with SessionLocal() as db:
        from app.models import SystemDoc

        for k in (created["key"], "notice_01"):
            d = db.query(SystemDoc).filter(SystemDoc.doc_key == k).first()
            if d:
                db.delete(d)
        db.commit()


def test_group_based_visibility(client):
    """两级权限：doc.view 控制菜单可见，Role.doc_groups 控制分组可见范围。

    例：仅授予 doc.view + doc_groups=['用户文档'] 的账号，只能看到「使用说明」。
    """
    with SessionLocal() as db:
        role = Role(
            id="role_doc_usr",
            name="仅用户文档",
            description="",
            scope="self",
            is_system=False,
            permissions=["doc.view"],  # 仅菜单权限，无编辑/新建/同步
            doc_groups=["用户文档"],
        )
        db.add(role)
        db.flush()
        u = User(
            id="U_DOC_TEST",
            name="文档测试",
            account="doctest",
            password_hash=hash_password("123456"),
            dept_id="CO",
            role_id="role_doc_usr",
            status="active",
        )
        db.add(u)
        db.commit()

    resp = client.post("/api/v1/auth/login", json={"account": "doctest", "password": "123456"})
    assert resp.status_code == 200
    h = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    r = client.get("/api/v1/system/docs", headers=h)
    assert r.status_code == 200
    keys = {d["key"] for d in r.json()}
    assert keys == {"usage"}  # 仅「用户文档」分组下的使用说明可见

    # 开发文档不可见 -> 404
    assert client.get("/api/v1/system/docs/prd", headers=h).status_code == 404
    # 无 doc.edit -> 编辑 403
    assert client.put("/api/v1/system/docs/usage", json={"content": "x"}, headers=h).status_code == 403
    # 无 doc.create -> 新建 403
    assert client.post("/api/v1/system/docs", json={"title": "x"}, headers=h).status_code == 403

    # 清理
    with SessionLocal() as db:
        db.delete(db.get(User, "U_DOC_TEST"))
        db.delete(db.get(Role, "role_doc_usr"))
        db.commit()


def test_member_sees_all_docs_without_restriction(client, member_headers):
    """普通成员默认拥有 doc.view 且 doc_groups 为空（全部分组），应能看到全部内置文档。"""
    r = client.get("/api/v1/system/docs", headers=member_headers)
    assert r.status_code == 200
    keys = {d["key"] for d in r.json()}
    assert BUILTIN_KEYS <= keys
    # 无 doc.edit -> 编辑 403
    assert client.put("/api/v1/system/docs/usage", json={"content": "x"}, headers=member_headers).status_code == 403


def test_sync_endpoint(client, admin_headers):
    """同步接口幂等可用，不抛错。"""
    r = client.post("/api/v1/system/docs/sync", headers=admin_headers)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert isinstance(r.json().get("synced"), int)
