"""系统配置 · 数据字典接口验证：种子预设 + 增删改 + 权限。"""
from __future__ import annotations


def test_dict_seed_presets_present(client, admin_headers):
    """种子预设：车辆型号 / 挂车型号两个字典，枚举值齐全且可后续修改。"""
    res = client.get("/api/v1/system/dicts", headers=admin_headers)
    assert res.status_code == 200
    by_code = {d["code"]: d for d in res.json()}
    assert "vehicle_model" in by_code
    assert "trailer_model" in by_code

    vm = by_code["vehicle_model"]
    assert vm["name"] == "车辆型号"
    assert [i["value"] for i in vm["items"]] == ["6*4牵引车", "4*2牵引车", "矿卡", "自卸车"]

    tm = by_code["trailer_model"]
    assert [i["value"] for i in tm["items"]] == ["侧翻挂", "高栏挂", "后翻挂"]

    # 电池容量字典（枚举值从线上同步：400度/423度/600度/352度），默认启用
    assert "battery_capacity" in by_code
    bc = by_code["battery_capacity"]
    assert bc["name"] == "电池容量"
    assert [i["value"] for i in bc["items"]] == ["400度", "423度", "600度", "352度"]
    assert bc.get("status", "active") == "active"

    # 按 code 过滤
    res2 = client.get("/api/v1/system/dicts?code=vehicle_model", headers=admin_headers)
    assert res2.status_code == 200
    assert len(res2.json()) == 1


def test_dict_crud_and_view_only_cannot_edit(client, admin_headers, member_headers):
    """管理员可增删改并整份替换枚举值；仅有查看权限的成员改操作被拒（403）。"""
    # 成员可查看
    assert client.get("/api/v1/system/dicts", headers=member_headers).status_code == 200
    # 成员不能新增
    r = client.post(
        "/api/v1/system/dicts",
        json={"name": "测试字典", "code": "battery", "items": [{"value": "A", "sort": 0}]},
        headers=member_headers,
    )
    assert r.status_code == 403

    # 管理员新增（带 code）
    r = client.post(
        "/api/v1/system/dicts",
        json={"name": "电池类型", "code": "battery", "items": [{"value": "磷酸铁锂", "sort": 0}, {"value": "三元锂", "sort": 1}]},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    assert [i["value"] for i in r.json()["items"]] == ["磷酸铁锂", "三元锂"]

    # 编码唯一：再建一个相同 code → 422
    r_dup = client.post(
        "/api/v1/system/dicts",
        json={"name": "重复编码", "code": "battery", "items": []},
        headers=admin_headers,
    )
    assert r_dup.status_code == 422

    # 管理员整份替换枚举值（编辑界面可增删多行）
    r2 = client.patch(
        f"/api/v1/system/dicts/{did}",
        json={"name": "电池类型", "items": [{"value": "钠离子", "sort": 0}]},
        headers=admin_headers,
    )
    assert r2.status_code == 200, r2.text
    assert [i["value"] for i in r2.json()["items"]] == ["钠离子"]

    # 已存在的配置不允许删除：删除接口已移除，返回 404/405，配置仍在（按 id 定位，避免 PATCH 未带 code 置空干扰）
    del_status = client.delete(f"/api/v1/system/dicts/{did}", headers=admin_headers).status_code
    assert del_status in (404, 405), del_status
    all_dicts = client.get("/api/v1/system/dicts", headers=admin_headers).json()
    assert any(d["id"] == did for d in all_dicts), "配置应仍在，不应被删除"

    # 停用：状态置为 disabled（前端据此把枚举值移出下拉，但配置不丢）
    r_off = client.post(f"/api/v1/system/dicts/{did}/status", json={"status": "disabled"}, headers=admin_headers)
    assert r_off.status_code == 200, r_off.text
    assert r_off.json()["status"] == "disabled"
    all_dicts = client.get("/api/v1/system/dicts", headers=admin_headers).json()
    target = next(d for d in all_dicts if d["id"] == did)
    assert target["status"] == "disabled"

    # 重新启用
    r_on = client.post(f"/api/v1/system/dicts/{did}/status", json={"status": "active"}, headers=admin_headers)
    assert r_on.status_code == 200, r_on.text
    assert r_on.json()["status"] == "active"

    # 非法 status 被拒
    r_bad = client.post(f"/api/v1/system/dicts/{did}/status", json={"status": "weird"}, headers=admin_headers)
    assert r_bad.status_code == 400
