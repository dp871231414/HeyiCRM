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

    # 删除
    assert client.delete(f"/api/v1/system/dicts/{did}", headers=admin_headers).status_code == 200
    by_code = {d["code"]: d for d in client.get("/api/v1/system/dicts", headers=admin_headers).json()}
    assert "battery" not in by_code
