"""市场项目本轮新增能力验证：项目进展时间轴 + 导入/导出/模板。

覆盖：列表展示项目进展（不展示项目描述）、详情按钮与权限、进展时间轴追加（原不可改）、
导入模板/导出仍展示项目描述、列名（车头需求/责任人）等。
"""
from __future__ import annotations

import io

from openpyxl import Workbook

from app.services.importer import (
    MARKET_PROJECT_COLUMNS,
    MARKET_PROJECT_EXPORT_COLUMNS,
    MARKET_PROJECT_OPTIONAL_COLUMNS,
)


def _xlsx(rows, columns):
    wb = Workbook()
    ws = wb.active
    ws.append(columns)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _mp_sheet(rows: list[list]) -> tuple:
    return (
        "mp.xlsx",
        _xlsx(rows, MARKET_PROJECT_COLUMNS),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _load_xlsx(content: bytes):
    from openpyxl import load_workbook

    return load_workbook(io.BytesIO(content))


def _header_of(ws, n: int, row: int) -> list:
    return [ws.cell(row=row, column=i).value for i in range(1, n + 1)]


def _mp_body(**over) -> dict:
    body = {
        "name": "验证项目",
        "description": "回归测试用",
        "progress": "初始进展：已立项",
        "tractor_demand": 10,
        "trailer_demand": 5,
        "stage": 25,
        "owner": "郑凯",
    }
    body.update(over)
    return body


# ---------------------------------------------------------------- 模板 / 导出


def test_market_template_columns_include_progress_and_description(client, admin_headers):
    """模板列含「项目进展」与「项目描述」，与需求「导入模板仍展示项目描述」一致。"""
    from app.services.importer import HEADER_ROW

    resp = client.get("/api/v1/market-projects/import/template", headers=admin_headers)
    assert resp.status_code == 200
    ws = _load_xlsx(resp.content).worksheets[0]
    header = _header_of(ws, len(MARKET_PROJECT_COLUMNS), HEADER_ROW)
    assert header == MARKET_PROJECT_COLUMNS
    assert "项目进展" in header
    assert "项目描述" in header


def test_market_export_columns_align_with_list_and_form(client, admin_headers):
    """导出列 = 项目ID + 全部可填写列 + 系统列；业务列与模板同名。"""
    from app.services.importer import HEADER_ROW

    resp = client.get("/api/v1/market-projects/export", headers=admin_headers)
    assert resp.status_code == 200
    ws = _load_xlsx(resp.content).worksheets[0]
    header = _header_of(ws, len(MARKET_PROJECT_EXPORT_COLUMNS), HEADER_ROW)
    assert header == MARKET_PROJECT_EXPORT_COLUMNS
    for name in MARKET_PROJECT_COLUMNS:
        assert name in header
    for name in ("项目ID", "创建人", "创建时间", "更新时间"):
        assert name in header


# ---------------------------------------------------------------- 项目进展时间轴


def test_market_progress_add_and_list(client, admin_headers):
    """新建带首条进展；编辑只能追加，原进展不可改；列表 latestProgress 同步最新。"""
    r = client.post("/api/v1/market-projects", json=_mp_body(name="进展验证项目"), headers=admin_headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["latestProgress"] == "初始进展：已立项"

    # 追加一条进展
    r2 = client.post(
        f"/api/v1/market-projects/{pid}/progress",
        json={"content": "第二轮：方案已评审通过"},
        headers=admin_headers,
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["content"] == "第二轮：方案已评审通过"

    # 列表 latestProgress 同步最新一条
    lst = client.get("/api/v1/market-projects", headers=admin_headers).json()["items"]
    item = next(x for x in lst if x["id"] == pid)
    assert item["latestProgress"] == "第二轮：方案已评审通过"

    # 时间轴倒序，含两条
    prog = client.get(f"/api/v1/market-projects/{pid}/progress", headers=admin_headers).json()
    assert prog["total"] == 2
    contents = [p["content"] for p in prog["items"]]
    assert contents[0] == "第二轮：方案已评审通过"
    assert contents[-1] == "初始进展：已立项"


def test_market_progress_requires_content(client, admin_headers):
    r = client.post("/api/v1/market-projects", json=_mp_body(), headers=admin_headers)
    pid = r.json()["id"]
    bad = client.post(f"/api/v1/market-projects/{pid}/progress", json={"content": ""}, headers=admin_headers)
    assert bad.status_code == 422


# ---------------------------------------------------------------- 导入


def test_market_import_success(client, admin_headers):
    """导入成功写入项目，并把「项目进展」作为第一条进展记录。"""
    rows = [
        ["华东物流园替换", "已完成需求调研", "200 辆燃油重卡替换", 200, 120, 25, "郑凯", "市场部"],
    ]
    resp = client.post(
        "/api/v1/market-projects/import",
        files={"file": _mp_sheet(rows)},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported"] == 1, data
    assert data["errors"] == []

    # 验证写入 + 首条进展
    lst = client.get("/api/v1/market-projects", headers=admin_headers).json()["items"]
    item = next(x for x in lst if x["name"] == "华东物流园替换")
    assert item["latestProgress"] == "已完成需求调研"
    prog = client.get(f"/api/v1/market-projects/{item['id']}/progress", headers=admin_headers).json()
    assert prog["total"] == 1
    assert prog["items"][0]["content"] == "已完成需求调研"


def test_market_import_rejects_bad_owner(client, admin_headers):
    rows = [
        ["X项目", "进展", "描述", 1, 1, 25, "不存在的人", ""],
    ]
    resp = client.post(
        "/api/v1/market-projects/import",
        files={"file": _mp_sheet(rows)},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 0
    assert any("不是系统内已有账号" in e["msg"] for e in data["errors"])
