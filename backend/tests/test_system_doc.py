"""文档中心接口测试：列表 / 获取 / 编辑 / 渲染 / 同步。"""
from __future__ import annotations


def test_list_docs(client, admin_headers):
    """文档中心至少包含 7 类文档，且每条带渲染后的 html 字段。"""
    r = client.get("/api/v1/system/docs", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    keys = {d["key"] for d in data}
    assert {"usage", "prd", "tech", "test", "design", "skill", "devnotes"} <= keys
    assert all("html" in d for d in data)


def test_get_doc_and_404(client, admin_headers):
    r = client.get("/api/v1/system/docs/prd", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["key"] == "prd"

    r = client.get("/api/v1/system/docs/not_exist", headers=admin_headers)
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


def test_sync_endpoint(client, admin_headers):
    """同步接口幂等可用，不抛错。"""
    r = client.post("/api/v1/system/docs/sync", headers=admin_headers)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert isinstance(r.json().get("synced"), int)
