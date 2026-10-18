"""Round 36 线上验证：文档中心（使用说明）菜单 + 文档存库自动更新。

- 登录拿 Cookie（线上代理改写 Authorization，必须用 Cookie 鉴权）
- 校验文档中心接口：列表 7 篇、usage 有内容、sync 刷新、编辑 version+1
- 校验前端 chunk 含「使用说明」菜单与 DocView 渲染
- 用临时编辑后通过 sync 还原，不污染生产
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


def login():
    s, _, c = req("POST", "/auth/login", body={"account": ADMIN[0], "password": ADMIN[1]})
    assert s == 200, f"login failed: {s}"
    m = re.search(r"access_token=([^;]+)", c)
    assert m, "no access_token in Set-Cookie"
    return m.group(1)


def main():
    tok = login()
    fails = []

    # 1) 列表 7 篇
    s, b = req("GET", "/system/docs", tok)[:2]
    docs = json.loads(b)
    keys = {d["key"] for d in docs}
    expect = {"usage", "prd", "tech", "test", "design", "skill", "devnotes"}
    if s != 200 or not expect <= keys:
        fails.append(f"[1] 文档列表异常 s={s} keys={keys}")
    else:
        print(f"[1] 文档中心列表 OK：{sorted(keys)}")

    # 2) usage 有渲染内容（bundled_docs 已加载）
    s, b = req("GET", "/system/docs/usage", tok)[:2]
    usage = json.loads(b)
    if s != 200 or not usage.get("html"):
        fails.append(f"[2] usage 文档无内容 s={s}")
    else:
        print(f"[2] usage 文档 OK：fmt={usage['fmt']} html长度={len(usage['html'])}")

    # 3) sync 刷新
    s, b = req("POST", "/system/docs/sync", tok)[:2]
    js = json.loads(b)
    if s != 200 or js.get("synced", 0) != 7:
        fails.append(f"[3] sync 异常 s={s} {js}")
    else:
        print(f"[3] sync OK：synced={js['synced']}")

    # 4) 编辑 prd 后 version+1，再 sync 还原
    before = next(d for d in docs if d["key"] == "prd")["version"]
    s, b = req("PUT", "/system/docs/prd", tok, {"content": "# 临时\n测试", "fmt": "markdown"})[:2]
    after = json.loads(b)
    if s != 200 or after["version"] <= before:
        fails.append(f"[4] 编辑 prd 异常 s={s} v={after.get('version')}")
    else:
        print(f"[4] 编辑 prd OK：version {before}→{after['version']}")
    # 还原
    req("POST", "/system/docs/sync", tok)
    print("    已通过 sync 还原 prd 内容")

    # 5) 前端 chunk 含「使用说明」菜单与 DocView
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
    if "使用说明" not in text:
        fails.append("[5] 前端未含「使用说明」菜单文案")
    else:
        print("[5] 前端含「使用说明」菜单 OK")
    if "DocView" not in text and "docApi" not in text:
        fails.append("[5] 前端未含 DocView/docApi")
    else:
        print("    前端含 DocView/docApi OK")

    if fails:
        print("\n❌ 验证失败：")
        for f in fails:
            print("  -", f)
        raise SystemExit(1)
    print("\n✅ Round 36 线上验证全部通过（文档中心 + 自动更新）")


if __name__ == "__main__":
    main()
