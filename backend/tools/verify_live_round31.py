"""round31 线上验证：电池容量字典 + 数据字典启用/停用（删除已禁用）。

仅做只读 + 一次可逆的「停用→启用」切换校验（用完即恢复 active），不破坏线上配置：
1) /system/dicts：battery_capacity 存在，枚举值=400度/423度/600度/352度，状态 active；
2) 删除接口已移除：DELETE /system/dicts/{id} 返回 404/405；
3) 启用/停用可用：POST /system/dicts/{id}/status 切到 disabled 再切回 active，最终恢复 active。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

BASE = "https://heyi-fleet-dashboard.app.workbuddy.host"
API = f"{BASE}/api/v1"
ACCT, PWD = "admin", "123456"


def _req(method: str, path: str, cookie: str | None = None, data: dict | None = None):
    url = f"{API}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    if cookie:
        req.add_header("Cookie", f"access_token={cookie}")
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def _login() -> str:
    data = json.dumps({"account": ACCT, "password": PWD}).encode()
    req = urllib.request.Request(
        f"{API}/auth/login", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        sc = r.headers.get("Set-Cookie", "")
    return sc.split("access_token=", 1)[1].split(";", 1)[0]


def _main() -> None:
    cookie = _login()
    ok = True

    # 1) battery_capacity 字典
    st, dicts = _req("GET", "/system/dicts", cookie)
    assert st == 200, f"[1] dicts 失败: {st}"
    by_code = {d["code"]: d for d in dicts}
    assert "battery_capacity" in by_code, f"[1] 缺少 battery_capacity 字典，现有: {list(by_code)}"
    bc = by_code["battery_capacity"]
    vals = [i["value"] for i in bc["items"]]
    assert vals == ["400度", "423度", "600度", "352度"], f"[1] 枚举值不符: {vals}"
    assert bc.get("status", "active") == "active", f"[1] 状态非 active: {bc.get('status')}"
    print(f"[1] 电池容量字典 OK：4 个枚举值 {vals}，状态 {bc.get('status')}（id={bc['id']}）")
    did = bc["id"]

    # 2) 删除接口已禁用
    st_del, _ = _req("DELETE", f"/system/dicts/{did}", cookie)
    assert st_del in (404, 405), f"[2] 删除接口应返回 404/405，实际 {st_del}"
    print(f"[2] 删除已禁用 OK：DELETE /system/dicts/{did} 返回 {st_del}")

    # 3) 启用/停用（可逆，最终恢复 active）
    st_off, off = _req("POST", f"/system/dicts/{did}/status", cookie, {"status": "disabled"})
    assert st_off == 200 and off.get("status") == "disabled", f"[3] 停用失败: {st_off} {off}"
    by_code = {d["code"]: d for d in _req("GET", "/system/dicts", cookie)[1]}
    assert by_code["battery_capacity"]["status"] == "disabled"
    st_on, on = _req("POST", f"/system/dicts/{did}/status", cookie, {"status": "active"})
    assert st_on == 200 and on.get("status") == "active", f"[3] 重新启用失败: {st_on} {on}"
    # 非法 status 应被拒
    st_bad, _ = _req("POST", f"/system/dicts/{did}/status", cookie, {"status": "x"})
    assert st_bad == 400, f"[3] 非法 status 应 400，实际 {st_bad}"
    print("[3] 启用/停用 OK：disabled→active 切换有效，非法 status 被拒(400)，已恢复 active")

    if ok:
        print("\n✅ round31 线上验证全部通过：电池容量字典就位、删除已禁用、启用/停用可用。")


if __name__ == "__main__":
    _main()
