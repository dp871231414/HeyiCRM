"""线上部署后 · Round 28 专项验证（责任人范围过滤 + 任务组联合唯一与删除 + 字段长度限制 + 项目描述必填）。

用法：PYTHONPATH=. python tools/verify_live_round28.py
所有新建数据（任务组）在验证结束前删除，不污染线上库。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

BASE = "https://heyi-fleet-dashboard.app.workbuddy.host"
API = f"{BASE}/api/v1"


def _login(account: str, password: str):
    url = f"{API}/auth/login"
    req = urllib.request.Request(
        url,
        data=json.dumps({"account": account, "password": password}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        set_cookie = resp.headers.get("Set-Cookie", "")
    assert "access_token=" in set_cookie, f"登录未下发 cookie: {set_cookie}"
    cookie = set_cookie.split("access_token=", 1)[1].split(";", 1)[0]
    return body, cookie


def _req(method, path, cookie, json_body=None):
    url = f"{API}{path}"
    data = None
    headers = {"Accept": "application/json"}
    headers["Cookie"] = f"access_token={cookie}"
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" not in ctype or not body:
                return resp.status, body
            return resp.status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def main():
    print(f"== 目标：{BASE} · Round 28 专项验证 ==")
    PW = "123456"

    # --- 1) admin 视角：责任人下拉应返回全部启用账号，且含 deptId ---
    _, admin_cookie = _login("admin", PW)
    st, body = _req("GET", "/meta/owners", admin_cookie)
    assert st == 200, f"/meta/owners 失败: {st} {body}"
    owners = body.get("owners", body) if isinstance(body, dict) else body
    assert isinstance(owners, list) and len(owners) >= 5, f"owner 数量异常: {owners}"
    assert all("deptId" in o for o in owners), f"owner 缺少 deptId: {owners[0]}"
    print(f"[1] admin /meta/owners OK，返回 {len(owners)} 个责任人（均含 deptId），admin 范围为 all")

    # --- 2) member(self) 视角：责任人下拉应只返回本人 ---
    _, member_cookie = _login("zhengkai", PW)
    st, body = _req("GET", "/meta/owners", member_cookie)
    assert st == 200, f"member /meta/owners 失败: {st} {body}"
    m_owners = body.get("owners", body) if isinstance(body, dict) else body
    assert len(m_owners) == 1 and m_owners[0]["name"] == "郑凯", \
        f"scope=self 应只返回本人，实际: {m_owners}"
    print(f"[2] zhengkai(self) /meta/owners OK，仅返回本人（{m_owners[0]['name']}），范围过滤生效")

    # --- 3) 项目描述必填：缺 description 应 422 ---
    st, body = _req("POST", "/market-projects", admin_cookie, json_body={
        "name": "R28-无描述项目", "progress": "初始", "stage": 25, "owner": "郑凯",
    })
    assert st == 422, f"缺描述应 422，实际: {st} {body}"
    print(f"[3] 项目描述必填 OK，缺 description 返回 422")

    # --- 4) 字段长度限制：名称>40 / 描述>150 / 进展>150 应 422 ---
    long_name = "项" * 41
    st, _ = _req("POST", "/market-projects", admin_cookie, json_body={
        "name": long_name, "description": "d", "progress": "p", "stage": 25, "owner": "郑凯",
    })
    assert st == 422, f"项目名>40 应 422，实际: {st}"
    long_desc = "描" * 151
    st, _ = _req("POST", "/market-projects", admin_cookie, json_body={
        "name": "R28-长度", "description": long_desc, "progress": "p", "stage": 25, "owner": "郑凯",
    })
    assert st == 422, f"项目描述>150 应 422，实际: {st}"
    long_prog = "进" * 151
    st, _ = _req("POST", "/market-projects", admin_cookie, json_body={
        "name": "R28-长度", "description": "d", "progress": long_prog, "stage": 25, "owner": "郑凯",
    })
    assert st == 422, f"项目进展>150 应 422，实际: {st}"
    print(f"[4] 项目字段长度限制 OK（名称>40 / 描述>150 / 进展>150 均 422）")

    # --- 5) 任务组：名称+责任人 联合唯一 + 可删除 ---
    owner_a = next(o for o in owners if o["name"] == "郑凯")
    owner_b = next((o for o in owners if o["name"] == "林雪"), owners[1])
    tg_name = "【R28-验证-待删除】任务组"
    # 5a) 建 A
    st, b1 = _req("POST", "/task-groups", admin_cookie,
                  json_body={"name": tg_name, "owner_id": owner_a["id"]})
    assert st in (200, 201), f"建任务组A 失败: {st} {b1}"
    id_a = b1["id"]
    # 5b) 同名不同责任人 B 应允许
    st, b2 = _req("POST", "/task-groups", admin_cookie,
                  json_body={"name": tg_name, "owner_id": owner_b["id"]})
    assert st in (200, 201), f"同名不同责任人应允许: {st} {b2}"
    id_b = b2["id"]
    # 5c) 同名同责任人 A 重复应 422
    st, _ = _req("POST", "/task-groups", admin_cookie,
                 json_body={"name": tg_name, "owner_id": owner_a["id"]})
    assert st == 422, f"同名同责任人重复应 422，实际: {st}"
    print(f"[5] 任务组联合唯一 OK（同名不同责任人并存、同名同责任人 422）")
    # 5d) 删除两个测试任务组
    for tid in (id_a, id_b):
        st, _ = _req("DELETE", f"/task-groups/{tid}", admin_cookie)
        assert st in (204, 200), f"删除任务组 {tid} 失败: {st}"
        st2, _ = _req("GET", f"/task-groups/{tid}", admin_cookie)
        assert st2 in (403, 404), f"删除后任务组应不可见: {st2}"
    print(f"[6] 任务组删除 OK（建→删→不可见）")

    # --- 7) 任务组名 >25 应 422 ---
    st, _ = _req("POST", "/task-groups", admin_cookie,
                 json_body={"name": "组" * 26, "owner_id": owner_a["id"]})
    assert st == 422, f"任务组名>25 应 422，实际: {st}"
    print(f"[7] 任务组名长度限制 OK（>25 返回 422）")

    print("\n✅ Round 28 线上专项验证全部通过：责任人范围过滤、项目描述必填、字段长度限制、任务组联合唯一与删除。")


if __name__ == "__main__":
    main()
