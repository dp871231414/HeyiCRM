"""Round 37 线上验证：文档中心分组 + 两级权限 + 视觉交互文档。

覆盖用户 Round 37 需求：
  1) 系统配置「使用说明」→「文档中心」，新增分组（doc_group 字典：默认/用户/开发文档）
  2) 两级权限：菜单 doc.view + 角色 doc_groups（空=全部，非空=仅指定分组）
  3) 视觉交互文档（visual）替代设计文档（design）
  5) 文档中心内容随源码刷新（/system/docs/sync）

鉴权：线上代理改写 Authorization，必须用登录下发的 HttpOnly Cookie 鉴权。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

BASE = "https://heyi-fleet-dashboard.app.workbuddy.host"
API = f"{BASE}/api/v1"
ADMIN = ("admin", "123456")


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Cookie"] = f"access_token={token}"
    r = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        return resp.status, resp.read().decode(), resp.headers.get("Set-Cookie")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers.get("Set-Cookie")


def login(account, password):
    s, b, c = req("POST", "/auth/login", body={"account": account, "password": password})
    assert s == 200, f"login failed: {s} {b}"
    m = re.search(r"access_token=([^;]+)", c)
    assert m, "no access_token in Set-Cookie"
    return m.group(1)


def main():
    tok = login(*ADMIN)
    fails = []

    # 0) 权限目录含 doc 分组（doc.view / doc.edit / doc.create / doc.sync）
    s, b = req("GET", "/permissions", tok)[:2]
    perms = json.loads(b)
    doc_perms = set()
    for g in perms.get("groups", []):
        if g.get("menu") == "doc":
            doc_perms = {p["key"] for p in g.get("items", [])}
    expect_doc = {"doc.view", "doc.edit", "doc.create", "doc.sync"}
    if s != 200 or not expect_doc <= doc_perms:
        fails.append(f"[0] 权限目录 doc 分组异常 s={s} perms={doc_perms}")
    else:
        print(f"[0] 权限目录 doc 分组 OK：{sorted(doc_perms)}")

    # 先 sync，确保文档中心内容与源码一致（无论 seed 是否预灌）
    s, b = req("POST", "/system/docs/sync", tok)[:2]
    js = json.loads(b)
    if s != 200 or js.get("synced", 0) != 7:
        fails.append(f"[1] sync 异常 s={s} {js}")
    else:
        print(f"[1] sync OK：synced={js['synced']}")

    # 2) 文档中心列表 7 篇，含分组字段，design 已移除，visual 存在
    s, b = req("GET", "/system/docs", tok)[:2]
    docs = json.loads(b)
    keys = {d["key"] for d in docs}
    expect = {"usage", "prd", "tech", "test", "visual", "skill", "devnotes"}
    has_group = all("group" in d for d in docs)
    if s != 200 or not expect <= keys:
        fails.append(f"[2] 文档列表异常 s={s} keys={keys}")
    elif not has_group:
        fails.append("[2] 文档列表缺少 group 字段")
    else:
        print(f"[2] 文档中心列表 OK：{sorted(keys)}（均含 group）")
        for d in docs:
            print(f"     - {d['key']:<10} group={d['group']:<6} ver={d['version']}")

    # 3) usage 有渲染内容
    s, b = req("GET", "/system/docs/usage", tok)[:2]
    usage = json.loads(b)
    if s != 200 or not usage.get("html"):
        fails.append(f"[3] usage 文档无内容 s={s}")
    else:
        print(f"[3] usage 文档 OK：group={usage.get('group')} html长度={len(usage['html'])}")

    # 4) design 已不可见
    s, _ = req("GET", "/system/docs/design", tok)[:2]
    if s != 404:
        fails.append(f"[4] design 应 404，实际 s={s}")
    else:
        print("[4] design 文档已下线 OK（404）")

    # 5) doc_group 数据字典：默认文档 / 用户文档 / 开发文档
    s, b = req("GET", "/system/dicts", tok)[:2]
    dicts = json.loads(b)
    dg = next((d for d in dicts if d.get("code") == "doc_group"), None)
    dg_items = set()
    if dg:
        for it in dg.get("items", []):
            if isinstance(it, dict):
                dg_items.add(it.get("value") or it.get("name") or it.get("code"))
            else:
                dg_items.add(it)
    if s != 200 or not {"默认文档", "用户文档", "开发文档"} <= dg_items:
        fails.append(f"[5] doc_group 字典异常 s={s} items={dg_items}")
    else:
        print(f"[5] doc_group 字典 OK：{sorted(dg_items)}")

    # 6) 两级权限：限定分组角色只能看对应分组文档
    role_name = "verify_r37"
    uname = "verify_r37_u"
    # 清理历史遗留测试角色 / 账号
    s, b = req("GET", "/roles", tok)[:2]
    for r in json.loads(b):
        if r.get("name") == role_name:
            req("DELETE", f"/roles/{r['id']}", tok)
    s, b = req("GET", "/users", tok)[:2]
    for u in json.loads(b):
        if u.get("account") == uname:
            req("DELETE", f"/users/{u['id']}", tok)
    # 创建限定分组角色（doc.view + docGroups=['用户文档']）
    s, b = req("POST", "/roles", tok, {
        "name": role_name,
        "permissions": ["doc.view"],
        "docGroups": ["用户文档"],
    })[:2]
    if s not in (200, 201):
        fails.append(f"[6] 创建限定分组角色失败 s={s} {b}")
    else:
        rid = json.loads(b)["id"]
        s, b = req("POST", "/users", tok, {
            "account": uname, "name": "验证账号", "password": "verify123",
            "dept_id": "CO", "role_id": rid, "scope": "self",
        })[:2]
        if s not in (200, 201):
            fails.append(f"[6] 创建限定分组账号失败 s={s} {b}")
        else:
            uid = json.loads(b)["id"]
            try:
                utok = login(uname, "verify123")
                s, b = req("GET", "/system/docs", utok)[:2]
                udocs = json.loads(b)
                ukeys = {d["key"] for d in udocs}
                if s != 200 or "usage" not in ukeys or "prd" in ukeys:
                    fails.append(f"[6] 两级权限异常：可见={ukeys}")
                else:
                    print(f"[6] 两级权限 OK：限定分组角色仅见 {sorted(ukeys)}（用户文档分组）")
            finally:
                req("DELETE", f"/users/{uid}", tok)
        req("DELETE", f"/roles/{rid}", tok)

    # 7) 前端 chunk 含「文档中心」、视觉交互文档替代设计文档
    html = urllib.request.urlopen(f"{BASE}/", timeout=30).read().decode()
    entries = set(re.findall(r'assets/([A-Za-z0-9_-]+\.js)', html))
    chunks = set(entries)
    for e in list(entries):
        try:
            c = urllib.request.urlopen(f"{BASE}/assets/{e}", timeout=30).read().decode(errors="ignore")
        except Exception:
            continue
        for m in re.findall(r'assets/([A-Za-z0-9_-]+\.js)', c):
            chunks.add(m)
    text = ""
    for c in chunks:
        try:
            text += urllib.request.urlopen(f"{BASE}/assets/{c}", timeout=30).read().decode(errors="ignore")
        except Exception:
            continue
    if "文档中心" not in text:
        fails.append("[7] 前端未含「文档中心」菜单文案")
    else:
        print("[7] 前端含「文档中心」菜单 OK")
    if "文档分组" not in text:
        fails.append("[7] 前端未含「文档分组」")
    else:
        print("    前端含「文档分组」可见范围 OK")

    if fails:
        print("\n❌ Round 37 线上验证失败：")
        for f in fails:
            print("  -", f)
        raise SystemExit(1)
    print("\n✅ Round 37 线上验证全部通过（文档中心分组 + 两级权限 + 视觉交互文档）")


if __name__ == "__main__":
    main()
