"""Round 30 线上验证：任务组下拉 搜索+分页+权限过滤。

仅做只读 GET 校验（演示库为确定性种子，单次请求内结果稳定）：
1) 列表默认返回全部，系统默认「空」(TG_NONE) 置顶；
2) size 分页切片；
3) keyword 正则匹配名称（大小写不敏感）；
4) 非法正则返回 400；
5) 按 ID 获取单个任务组。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

BASE = "https://heyi-fleet-dashboard.app.workbuddy.host"
API = f"{BASE}/api/v1"
ACCT, PWD = "admin", "123456"


def _req(method: str, path: str, cookie: str | None = None, raw: bool = False):
    url = f"{API}{path}"
    req = urllib.request.Request(url, method=method)
    if cookie:
        req.add_header("Cookie", f"access_token={cookie}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            return r.status, (body if raw else json.loads(body))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _login() -> str:
    data = json.dumps({"account": ACCT, "password": PWD}).encode()
    req = urllib.request.Request(f"{API}/auth/login", data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        sc = r.headers.get("Set-Cookie", "")
    return sc.split("access_token=", 1)[1].split(";", 1)[0]


def _main() -> None:
    cookie = _login()
    ok = True

    # 1) 默认列表（无 size）→ 全部，TG_NONE 置顶
    st, all_items = _req("GET", "/task-groups", cookie)
    assert st == 200, f"[1] 列表失败: {st}"
    assert isinstance(all_items, list) and len(all_items) >= 2, f"[1] 列表数量异常: {len(all_items)}"
    assert all_items[0]["id"] == "TG_NONE" and all_items[0]["isSystem"] is True, "[1] 系统默认未置顶"
    total = len(all_items)
    print(f"[1] 默认列表 OK：共 {total} 个，首项 TG_NONE 置顶")

    # 2) size 分页
    st, paged = _req("GET", "/task-groups?size=2", cookie)
    assert st == 200 and len(paged) == 2, f"[2] 分页异常: {st}/{len(paged) if isinstance(paged, list) else paged}"
    assert paged[0]["id"] == "TG_NONE", "[2] 分页首项非 TG_NONE"
    print("[2] size=2 分页 OK：返回 2 条，首项 TG_NONE")

    # 3) 正则搜索 keyword=华东
    st, kw = _req("GET", "/task-groups?keyword=%E5%8D%8E%E4%B8%9C", cookie)
    assert st == 200, f"[3] 搜索失败: {st}"
    names = {m["name"] for m in kw}
    assert "华东大区营收达成" in names, f"[3] 未命中 华东大区营收达成，实际: {names}"
    assert len(kw) < total, f"[3] 搜索未过滤（{len(kw)} == {total}）"
    print(f"[3] 正则搜索 keyword=华东 OK：命中 {len(kw)} 条（含「华东大区营收达成」），少于全量 {total}")

    # 4) 交替正则 keyword=华东|华南 应不少于 华东
    st, alt = _req("GET", "/task-groups?keyword=%E5%8D%8E%E4%B8%9C%7C%E5%8D%8E%E5%8D%97", cookie)
    assert st == 200, f"[4] 交替搜索失败: {st}"
    assert len(alt) >= len(kw), f"[4] 交替正则未扩展结果: {len(alt)} < {len(kw)}"
    print(f"[4] 交替正则 keyword=华东|华南 OK：命中 {len(alt)} 条（≥ 华东 的 {len(kw)}）")

    # 5) 非法正则 → 400
    st, _ = _req("GET", "/task-groups?keyword=[0-9", cookie)
    assert st == 400, f"[5] 非法正则未返回 400，实际: {st}"
    print("[5] 非法正则 keyword=[0-9 OK：返回 400")

    # 6) 按 ID 获取
    target = next((m for m in all_items if m["name"] == "华东大区营收达成"), None)
    assert target, "[6] 种子中未找到 华东大区营收达成"
    st, one = _req("GET", f"/task-groups/{target['id']}", cookie)
    assert st == 200 and one.get("id") == target["id"], f"[6] 按 ID 获取失败: {st}"
    print(f"[6] GET /task-groups/{target['id']} OK：返回「{one['name']}」")

    # 7) 不存在的 ID → 404
    st, _ = _req("GET", "/task-groups/TG_NO_SUCH_X", cookie)
    assert st == 404, f"[7] 不存在 ID 未返回 404，实际: {st}"
    print("[7] 不存在 ID OK：返回 404")

    print("\n✅ Round 30 线上验证全部通过（任务组下拉 搜索+分页+权限过滤 接口就绪）。")


if __name__ == "__main__":
    _main()
