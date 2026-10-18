"""清空线上业务数据后的验证：仅保留 admin(显示名「管理员」)，任务/项目/指标数据清零，指标定义目录保留。

仅做只读 GET 校验：
1) /meta/owners：仅 1 个账号，名为「管理员」、account=admin；
2) /tasks：0 条；
3) /market-projects：0 条；
4) /metrics/periods：空列表（证明指标实际值已清空）；
5) /metrics/defs：保留指标定义目录（>=20 条）。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

BASE = "https://heyi-fleet-dashboard.app.workbuddy.host"
API = f"{BASE}/api/v1"
ACCT, PWD = "admin", "123456"


def _req(method: str, path: str, cookie: str | None = None):
    url = f"{API}{path}"
    req = urllib.request.Request(url, method=method)
    if cookie:
        req.add_header("Cookie", f"access_token={cookie}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _login() -> str:
    data = json.dumps({"account": ACCT, "password": PWD}).encode()
    req = urllib.request.Request(
        f"{API}/auth/login", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        sc = r.headers.get("Set-Cookie", "")
    return sc.split("access_token=", 1)[1].split(";", 1)[0]


def _items(resp):
    if isinstance(resp, dict):
        if "items" in resp:
            return resp["items"], resp.get("total", len(resp["items"]))
        if "data" in resp and isinstance(resp["data"], list):
            return resp["data"], len(resp["data"])
    return resp, len(resp) if isinstance(resp, list) else 0


def _main() -> None:
    cookie = _login()

    # 1) 账号：仅 1 个，名为「管理员」、id=U001（平台管理员）
    st, owners = _req("GET", "/meta/owners", cookie)
    assert st == 200, f"[1] owners 失败: {st}"
    assert isinstance(owners, list) and len(owners) == 1, f"[1] 账号数应为 1，实际 {len(owners)}"
    assert owners[0]["name"] == "管理员" and owners[0]["id"] == "U001", (
        f"[1] 管理员名/id 异常: {owners[0]}"
    )
    print(f"[1] 账号 OK：仅 1 个，名为「管理员」(id=U001)")

    # 2) 任务：0 条
    st, tasks = _req("GET", "/tasks", cookie)
    assert st == 200, f"[2] tasks 失败: {st}"
    _, total = _items(tasks)
    assert total == 0, f"[2] 任务未清空: total={total}"
    print("[2] 任务 OK：0 条")

    # 3) 市场项目：0 条
    st, mps = _req("GET", "/market-projects", cookie)
    assert st == 200, f"[3] market-projects 失败: {st}"
    _, total = _items(mps)
    assert total == 0, f"[3] 项目未清空: total={total}"
    print("[3] 市场项目 OK：0 条")

    # 4) 指标实际值/目标值已清空：仪表盘看板每行 actual(及 annual 的 target) 均为 None
    st, board = _req("GET", "/metrics/board", cookie)
    assert st == 200, f"[4] metrics/board 失败: {st}"
    rows = list(board.get("annual", [])) + list(board.get("monitor", []))
    bad = [r.get("name") for r in rows if r.get("actual") is not None]
    bad_t = [r.get("name") for r in board.get("annual", []) if r.get("target") is not None]
    assert not bad, f"[4] 仍有指标实际值非空: {bad}"
    assert not bad_t, f"[4] 仍有指标目标值非空: {bad_t}"
    print(f"[4] 指标数据 OK：看板 {len(rows)} 行 actual/target 均为空（实际值/目标值已清空）")

    # 5) 指标定义目录：保留
    st, defs = _req("GET", "/metrics/defs", cookie)
    assert st == 200, f"[5] metrics/defs 失败: {st}"
    assert isinstance(defs, list) and len(defs) >= 20, f"[5] 指标定义过少: {len(defs)}"
    print(f"[5] 指标定义 OK：保留 {len(defs)} 条（目录未删）")

    print("\n✅ 线上清空验证全部通过：仅 admin(管理员)，任务/项目/指标数据清零，指标定义保留。")


if __name__ == "__main__":
    _main()
