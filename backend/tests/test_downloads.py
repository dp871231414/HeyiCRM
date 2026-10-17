"""下载中心：导出生成记录、列表、文件下载、删除、创建人隔离。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from io import BytesIO

from openpyxl import load_workbook


def _is_xlsx(content: bytes) -> bool:
    if content[:2] != b"PK":
        return False
    try:
        load_workbook(BytesIO(content))
        return True
    except Exception:
        return False


def test_task_export_creates_record_and_lists(client, admin_headers, member_headers):
    # admin 导出任务清单 → 先在下载中心生成一条记录（返回记录 JSON，不再即时下载文件）
    resp = client.get("/api/v1/tasks/export", headers=admin_headers)
    assert resp.status_code == 200
    rec = resp.json()
    assert rec["objectType"] == "task"
    assert rec["filename"].startswith("重点任务_") and rec["filename"].endswith(".xlsx")
    assert rec["createdByName"]  # 创建人姓名非空
    rid = rec["id"]

    # 列表也应包含该记录（按创建时间倒序，最新一条）
    lst = client.get("/api/v1/downloads", headers=admin_headers)
    assert lst.status_code == 200
    items = lst.json()
    assert any(r["id"] == rid for r in items), "导出后应在下载中心生成记录"

    # 文件可下载且为合法 xlsx
    f = client.get(f"/api/v1/downloads/{rid}/file", headers=admin_headers)
    assert f.status_code == 200
    assert _is_xlsx(f.content)

    # 成员看不到 admin 的记录（按创建人隔离）
    other = client.get("/api/v1/downloads", headers=member_headers)
    assert other.status_code == 200
    assert all(r["id"] != rid for r in other.json())


def test_market_export_isolated_from_other_user(client, admin_headers, member_headers):
    # admin 导出市场项目清单 → 生成 market_project 记录
    resp = client.get("/api/v1/market-projects/export", headers=admin_headers)
    assert resp.status_code == 200
    rec = resp.json()
    assert rec["objectType"] == "market_project"
    assert rec["filename"].startswith("市场项目_") and rec["filename"].endswith(".xlsx")
    rid = rec["id"]

    # 创建人本人（admin）可下载
    assert client.get(f"/api/v1/downloads/{rid}/file", headers=admin_headers).status_code == 200
    # 其他用户（member）下载返回 403
    assert client.get(f"/api/v1/downloads/{rid}/file", headers=member_headers).status_code == 403


def test_delete_record_removes_file(client, admin_headers):
    rec = client.get("/api/v1/tasks/export", headers=admin_headers).json()
    rid = rec["id"]

    d = client.delete(f"/api/v1/downloads/{rid}", headers=admin_headers)
    assert d.status_code == 204

    after = client.get("/api/v1/downloads", headers=admin_headers).json()
    assert all(r["id"] != rid for r in after)
    # 文件已删除 → 下载返回 404
    assert client.get(f"/api/v1/downloads/{rid}/file", headers=admin_headers).status_code == 404


def test_unauthenticated_list_rejected():
    # 用全新 client（不带任何会话 cookie）验证未登录被拒
    anon = TestClient(app)
    assert anon.get("/api/v1/downloads").status_code in (401, 403)
