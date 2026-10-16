"""用户偏好接口测试 · GET/PUT /auth/preferences。

覆盖：读取默认偏好、更新行高、非法取值被忽略、随账号持久化（/auth/me 回带）。
"""
from tests.conftest import login


def test_get_preferences_default_empty(client):
    headers, _ = login(client, "admin")
    resp = client.get("/api/v1/auth/preferences", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["preferences"] == {}


def test_update_row_height_persists(client):
    headers, _ = login(client, "admin")
    resp = client.put("/api/v1/auth/preferences", json={"preferences": {"rowHeight": "high"}}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["preferences"].get("rowHeight") == "high"

    # 再次读取应已持久化
    again = client.get("/api/v1/auth/preferences", headers=headers)
    assert again.json()["preferences"].get("rowHeight") == "high"

    # /auth/me 应回带偏好
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["user"]["preferences"].get("rowHeight") == "high"


def test_invalid_row_height_ignored(client):
    headers, _ = login(client, "zhengkai")
    # 非法取值不在白名单，应被忽略、保持原值（此处原为默认空）
    resp = client.put("/api/v1/auth/preferences", json={"preferences": {"rowHeight": "extreme"}}, headers=headers)
    assert resp.status_code == 200
    assert "rowHeight" not in resp.json()["preferences"]

    # 非法键同样被忽略
    resp2 = client.put("/api/v1/auth/preferences", json={"preferences": {"theme": "dark"}}, headers=headers)
    assert "theme" not in resp2.json()["preferences"]


def test_preferences_scoped_per_user(client):
    """不同账号的偏好相互独立：admin 改 high 不影响郑凯的默认。"""
    admin_h, _ = login(client, "admin")
    member_h, _ = login(client, "zhengkai")

    client.put("/api/v1/auth/preferences", json={"preferences": {"rowHeight": "ultra"}}, headers=admin_h)

    member_prefs = client.get("/api/v1/auth/preferences", headers=member_h).json()["preferences"]
    assert member_prefs.get("rowHeight", "default") != "ultra"
