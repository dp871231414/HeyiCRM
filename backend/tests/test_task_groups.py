"""任务组（原任务分类）与任务任务组关联测试。"""
from __future__ import annotations

from tests.conftest import login


# ---------------------------------------------------------------- 任务组 CRUD


def test_task_groups_list_includes_system_none(client, admin_headers):
    resp = client.get("/api/v1/task-groups", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()
    # 系统默认「空」始终存在，且排在首位
    assert items[0]["isSystem"] is True
    assert items[0]["id"] == "TG_NONE"
    assert items[0]["name"] == "空"
    # 新增字段随任务组单独建表维护：责任人 / 责任部门 / 更新时间
    for m in items:
        assert "ownerId" in m and "ownerName" in m
        assert "deptId" in m and "deptName" in m
        assert "updatedAt" in m
    # 演示数据里出现的「任务分类」已建为任务组
    names = {m["name"] for m in items}
    assert "华东大区营收达成" in names


def test_create_task_group_generates_id_and_creator(client, admin_headers):
    resp = client.post("/api/v1/task-groups", json={"name": "新能源运力专项"}, headers=admin_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("TG")
    assert body["id"] != "TG_NONE"
    assert body["name"] == "新能源运力专项"
    assert body["createdBy"] == "U001"
    assert body["createdAt"]


def test_create_task_group_duplicate_409(client, admin_headers):
    client.post("/api/v1/task-groups", json={"name": "重复任务组"}, headers=admin_headers)
    resp = client.post("/api/v1/task-groups", json={"name": "重复任务组"}, headers=admin_headers)
    assert resp.status_code == 409


def test_rename_task_group_keeps_id(client, admin_headers):
    created = client.post("/api/v1/task-groups", json={"name": "待改名任务组"}, headers=admin_headers).json()
    mt_id = created["id"]
    resp = client.patch(f"/api/v1/task-groups/{mt_id}", json={"name": "已改名任务组"}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == mt_id  # ID 不变
    assert resp.json()["name"] == "已改名任务组"


# ---------------------------------------------------------------- 任务关联任务组


def _create_task(client, headers, task_group_id):
    return client.post(
        "/api/v1/tasks",
        json={
            "parent": "任务组关联测试任务",
            "task_group_id": task_group_id,
            "abnormal": False,
            "target": 100,
            "done": 0,
            "note": "首条进展",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "dept_id": "D01",
            "owner": "郑凯",
        },
        headers=headers,
    )


def test_create_task_links_task_group(client, admin_headers):
    mt = client.post("/api/v1/task-groups", json={"name": "关联用任务组"}, headers=admin_headers).json()
    resp = _create_task(client, admin_headers, mt["id"])
    assert resp.status_code == 201
    body = resp.json()
    assert body["taskGroupId"] == mt["id"]
    assert body["taskGroupName"] == "关联用任务组"


def test_create_task_defaults_to_none_task_group(client, admin_headers):
    resp = _create_task(client, admin_headers, None)
    assert resp.status_code == 201
    assert resp.json()["taskGroupId"] == "TG_NONE"


def test_task_list_exposes_task_group_and_owner_id(client, admin_headers):
    # 演示数据 T202601 属市场部 D01，任务组应为「华东大区营收达成」
    resp = client.get("/api/v1/tasks?keyword=T202601", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items, "应至少有一条演示任务"
    t = items[0]
    assert "taskGroupId" in t and "taskGroupName" in t and "ownerId" in t
    assert t["taskGroupName"] == "华东大区营收达成"
    assert t["ownerId"]  # 责任人郑凯应有对应 user.id


# ---------------------------------------------------------------- 任务组责任人/部门回填（#2）


def test_task_group_backfilled_from_first_task(client, admin_headers):
    # 新建任务组（初始无责任人/部门）
    mt = client.post("/api/v1/task-groups", json={"name": "回填测试任务组"}, headers=admin_headers).json()
    assert mt["ownerId"] == ""
    assert mt["deptId"] == ""
    # 首个关联任务：责任人 郑凯(U006) / 部门 D01 → 回填到任务组
    resp = _create_task(client, admin_headers, mt["id"])
    assert resp.status_code == 201
    items = {m["id"]: m for m in client.get("/api/v1/task-groups", headers=admin_headers).json()}
    back = items[mt["id"]]
    assert back["ownerId"] == "U006"
    assert back["ownerName"] == "郑凯"
    assert back["deptId"] == "D01"
    assert back["deptName"] == "市场部"


def test_none_task_group_never_backfilled(client, admin_headers):
    # 「空」(TG_NONE) 不参与回填，始终无责任人/部门
    _create_task(client, admin_headers, None)
    item = {m["id"]: m for m in client.get("/api/v1/task-groups", headers=admin_headers).json()}["TG_NONE"]
    assert item["ownerId"] == ""
    assert item["deptId"] == ""


# ---------------------------------------------------------------- 列表分页 / 正则搜索（Round 30）


def test_task_groups_list_pagination(client, admin_headers):
    # 默认（不带 size）返回全部；带 size 则分页切片，且系统默认「空」始终置顶
    all_items = client.get("/api/v1/task-groups", headers=admin_headers).json()
    assert isinstance(all_items, list) and len(all_items) > 2
    assert all_items[0]["id"] == "TG_NONE"

    paged = client.get("/api/v1/task-groups?size=2", headers=admin_headers).json()
    assert len(paged) == 2
    assert paged[0]["id"] == "TG_NONE"  # 置顶


def test_task_groups_list_regex_search(client, admin_headers):
    # 正则匹配名称（大小写不敏感）：华东 应命中「华东大区营收达成」等
    resp = client.get("/api/v1/task-groups?keyword=华东", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()
    names = {m["name"] for m in items}
    assert "华东大区营收达成" in names
    # 过滤生效：结果应少于全量
    total = len(client.get("/api/v1/task-groups", headers=admin_headers).json())
    assert len(items) < total
    # 交替正则：华东|华南 至少命中两类
    alt = client.get("/api/v1/task-groups?keyword=华东|华南", headers=admin_headers).json()
    assert len(alt) >= len(items)


def test_task_groups_list_invalid_regex_400(client, admin_headers):
    # 非法正则（未闭合的字符类）应返回 400
    resp = client.get("/api/v1/task-groups?keyword=[0-9", headers=admin_headers)
    assert resp.status_code == 400


def test_task_group_get_by_id_and_404(client, admin_headers):
    created = client.post("/api/v1/task-groups", json={"name": "按ID获取测试组"}, headers=admin_headers).json()
    mt_id = created["id"]
    resp = client.get(f"/api/v1/task-groups/{mt_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == mt_id
    # 不存在返回 404
    assert client.get("/api/v1/task-groups/TG_NO_SUCH", headers=admin_headers).status_code == 404
