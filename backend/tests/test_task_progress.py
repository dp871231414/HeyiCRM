"""进展记录（时间轴）与任务详情权限测试 · round 18。

覆盖：
1. 新建任务时进展描述必填，并成为第一条进展记录；
2. 编辑任务不影响进展描述，只能通过「新增进展」追加；
3. 进展记录按时间倒序分页（默认 5 条，下拉加载）；
4. task.detail 权限默认授予所有角色（含自定义角色），详情/进展接口可访问。
"""
from __future__ import annotations

from tests.conftest import login


def _create_task(client, headers, note: str = "首条进展", parent: str = "进展测试任务"):
    resp = client.post(
        "/api/v1/tasks",
        json={
            "parent": parent,
            "description": "用于进展记录测试",
            "abnormal": False,
            "target": 100,
            "done": 0,
            "note": note,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "dept_id": "D01",
            "owner": "郑凯",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------- 进展描述必填 + 首条记录


def test_create_task_requires_note(client, admin_headers):
    resp = client.post(
        "/api/v1/tasks",
        json={
            "parent": "缺进展描述任务", "description": "", "abnormal": False,
            "target": 1, "done": 0, "note": "",
            "start_date": "2026-01-01", "end_date": "2026-12-31",
            "dept_id": "D01", "owner": "郑凯",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422


def test_create_task_writes_first_progress(client, admin_headers):
    task = _create_task(client, admin_headers, note="开工首周完成备料")
    assert task["latestProgress"] == "开工首周完成备料"
    page = client.get(f"/api/v1/tasks/{task['id']}/progress", headers=admin_headers).json()
    assert page["total"] == 1
    assert page["items"][0]["content"] == "开工首周完成备料"
    assert page["items"][0]["createdByName"] == "管理员"
    # 清理
    client.delete(f"/api/v1/tasks/{task['id']}", headers=admin_headers)


# ---------------------------------------------------------------- 编辑不改进展，只能追加


def test_update_task_keeps_note_and_appends_progress(client, admin_headers):
    task = _create_task(client, admin_headers, note="第一周进展")
    tid = task["id"]
    # 编辑任务其他字段：进展描述不受影响、也不新增记录
    upd = client.patch(
        f"/api/v1/tasks/{tid}",
        json={
            "parent": task["parent"], "description": task["description"], "abnormal": False,
            "target": 100, "done": 50, "note": "试图直接改进展",
            "start_date": "2026-01-01", "end_date": "2026-12-31",
            "dept_id": "D01", "owner": "郑凯",
        },
        headers=admin_headers,
    )
    assert upd.status_code == 200
    assert upd.json()["latestProgress"] == "第一周进展"  # 未被编辑修改
    # 通过「新增进展」追加
    add = client.post(f"/api/v1/tasks/{tid}/progress", json={"content": "第二周进展"}, headers=admin_headers)
    assert add.status_code == 201
    assert add.json()["content"] == "第二周进展"
    detail = client.get(f"/api/v1/tasks/{tid}", headers=admin_headers).json()
    assert detail["latestProgress"] == "第二周进展"  # 快照更新为最新一条
    page = client.get(f"/api/v1/tasks/{tid}/progress", headers=admin_headers).json()
    assert page["total"] == 2
    assert [i["content"] for i in page["items"]] == ["第二周进展", "第一周进展"]  # 倒序
    # 空内容拒绝
    assert client.post(f"/api/v1/tasks/{tid}/progress", json={"content": " "}, headers=admin_headers).status_code == 422
    client.delete(f"/api/v1/tasks/{tid}", headers=admin_headers)


def test_progress_pagination(client, admin_headers):
    task = _create_task(client, admin_headers, note="第1条", parent="进展分页任务")
    tid = task["id"]
    for i in range(2, 9):
        assert client.post(f"/api/v1/tasks/{tid}/progress", json={"content": f"第{i}条"}, headers=admin_headers).status_code == 201
    p1 = client.get(f"/api/v1/tasks/{tid}/progress", params={"page": 1, "size": 5}, headers=admin_headers).json()
    assert p1["total"] == 8 and len(p1["items"]) == 5
    assert p1["items"][0]["content"] == "第8条"
    p2 = client.get(f"/api/v1/tasks/{tid}/progress", params={"page": 2, "size": 5}, headers=admin_headers).json()
    assert len(p2["items"]) == 3 and p2["items"][-1]["content"] == "第1条"
    client.delete(f"/api/v1/tasks/{tid}", headers=admin_headers)


# ---------------------------------------------------------------- task.detail 权限


def test_task_detail_perm_granted_to_all_roles(client, admin_headers):
    """所有角色（内置 + 自定义）默认获得 task.detail。"""
    from app.db.session import SessionLocal
    from app.models import Role

    with SessionLocal() as db:
        roles = db.query(Role).all()
        assert roles, "种子数据应含角色"
        for r in roles:
            assert "task.detail" in (r.permissions or []), f"角色 {r.id} 缺 task.detail"
    # 权限清单（角色配置界面数据源）包含该权限点
    catalog = client.get("/api/v1/permissions", headers=admin_headers).json()
    task_keys = {i["key"] for g in catalog["groups"] if g["menu"] == "task" for i in g["items"]}
    assert "task.detail" in task_keys


def test_member_can_view_task_detail_and_progress(client, member_headers):
    """普通成员默认有 task.detail：可看任务详情与进展记录（数据范围仍按 scope 过滤）。"""
    me = client.get("/api/v1/auth/me", headers=member_headers).json()
    assert "task.detail" in me["perms"]
    # 郑凯（U006，D01）可见自己的演示任务 T202601
    detail = client.get("/api/v1/tasks/T202601", headers=member_headers)
    assert detail.status_code == 200
    progress = client.get("/api/v1/tasks/T202601/progress", headers=member_headers)
    assert progress.status_code == 200
    assert progress.json()["total"] >= 1
