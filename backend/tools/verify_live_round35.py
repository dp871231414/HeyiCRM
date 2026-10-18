"""线上验证 round35：车头/挂车「预估消化数量」为整数（车辆数不保留小数）。

走登录下发的 Cookie 鉴权（部署反代会改写 Authorization 头）。
- 需求分析只纳入「负责人属于市场部子树」的项目，故临时项目 owner 用可解析到市场树的人员（胡启迪）。
- 验证后删除临时项目，不污染生产。
"""
import json
import re
import urllib.request
import urllib.error

BASE = "https://heyi-fleet-dashboard.app.workbuddy.host"
API = f"{BASE}/api/v1"

_created = []


def req(method, path, token=None, json_body=None):
    url = API + path if path.startswith("/") else path
    data = json.dumps(json_body).encode() if json_body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Cookie"] = f"access_token={token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        return resp.status, resp.read().decode(), resp.headers.get("Set-Cookie")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers.get("Set-Cookie")


def cleanup(token):
    for p in list(_created):
        try:
            s, _, _ = req("DELETE", f"/market-projects/{p}", token)
            print(f"  删除 {p} -> {s}")
        except Exception as e:
            print(f"  删除 {p} 失败: {e}")
        _created.remove(p)


print("=== [1] 登录 admin ===")
s, body, cookie = req("POST", "/auth/login", json_body={"account": "admin", "password": "123456"})
assert s == 200, f"login failed {s}: {body}"
token = re.search(r"access_token=([^;]+)", cookie or "").group(1)
print("  OK")

# 清理上一轮失败留下的孤儿临时项目
print("=== [2] 清理历史孤儿临时项目 ===")
s, b, _ = req("GET", "/market-projects?size=200", token)
for it in json.loads(b).get("items", []):
    if it["name"].startswith("R35校验"):
        s2, _, _ = req("DELETE", f"/market-projects/{it['id']}", token)
        print(f"  删除孤儿 {it['id']} -> {s2}")

try:
    print("=== [3] 创建临时项目(stage=25, qty=10, owner=胡启迪) ===")
    # 阶段 25 → 默认转化率 0.25；预估消化 = 10 × 0.25 = 2.5 → 应四舍五入为 3（整数）
    body = {
        "name": "R35校验临时项目",
        "description": "线上验证用，创建后删除",
        "progress": "初始进展：临时校验",
        "stage": 25,
        "owner": "胡启迪",  # 可解析到市场部子树，确保落入需求分析范围
        "tractorRequirements": [{"model": "R35牵引车", "battery": "400度", "qty": 10}],
        "trailerRequirements": [{"model": "R35挂车", "qty": 10}],
    }
    s, b, _ = req("POST", "/market-projects", token, json_body=body)
    assert s == 201, f"create failed {s}: {b}"
    pid = json.loads(b)["id"]
    _created.append(pid)
    print(f"  OK pid={pid}")

    print("=== [4] 车辆需求分析：预估消化数量应为整数 3 ===")
    s, b, _ = req("GET", "/dashboard/demand-analysis", token)
    assert s == 200, f"demand-analysis failed {s}: {b}"
    da = json.loads(b)

    t = da["tractor"]["all"]
    row = next((x for x in t if x["model"] == "R35牵引车" and x["battery"] == "400度"), None)
    assert row is not None, f"车头组合未出现；当前 tractor.all={t}"
    print(f"  车头 预估消化 = {row['digest']} (qty={row['qty']})")
    assert isinstance(row["digest"], int) and not isinstance(row["digest"], bool), "digest 必须是整数"
    assert row["digest"] == 3, f"车头预估消化应为 3（2.5 四舍五入），实际 {row['digest']}"

    tr = da["trailer"]["all"]
    trow = next((x for x in tr if x["model"] == "R35挂车"), None)
    assert trow is not None, f"挂车未出现；当前 trailer.all={tr}"
    print(f"  挂车 预估消化 = {trow['digest']} (qty={trow['qty']})")
    assert isinstance(trow["digest"], int) and not isinstance(trow["digest"], bool)
    assert trow["digest"] == 3, f"挂车预估消化应为 3，实际 {trow['digest']}"

    # 全部 digest 字段均为整数（含既有数据）
    all_ok = all(isinstance(x["digest"], int) for x in t) and all(isinstance(x["digest"], int) for x in tr)
    assert all_ok, "存在非整数 digest"

    print("=== [5] 阶段元信息仍含流失(0)且转化率 0% ===")
    stages = da["stages"]
    assert [x["stage"] for x in stages] == [10, 25, 50, 75, 90, 100, 0], stages
    churn = next(x for x in stages if x["stage"] == 0)
    assert churn["prob"] == 0, churn
    print("  阶段列表与流失转化率 OK")

    print("=== [6] 前端构建已改为整数显示（线上 chunk 含 digest,0) 渲染）===")
    html = urllib.request.urlopen(f"{BASE}/", timeout=30).read().decode()
    entries = set(re.findall(r'assets/([A-Za-z0-9_-]+\.js)', html))
    # 入口 chunk 通过动态 import 引用懒加载块（如 DashboardView），需顺着引用收集全部 chunk
    all_chunks = set(entries)
    for e in list(entries):
        try:
            c = urllib.request.urlopen(f"{BASE}/assets/{e}", timeout=30).read().decode(errors="ignore")
        except Exception:
            continue
        for m in re.findall(r'assets/([A-Za-z0-9_-]+\.js)', c):
            all_chunks.add(m)
    found = False
    for c in all_chunks:
        try:
            chunk = urllib.request.urlopen(f"{BASE}/assets/{c}", timeout=30).read().decode(errors="ignore")
        except Exception:
            continue
        # 新构建：明细行预估消化用 fmt(r.digest, 0)；旧构建是 fmt(r.digest, 1)
        if "digest,0))" in chunk or "digest, 0))" in chunk:
            found = True
            break
    assert found, "线上前端未含整数渲染（digest,0)），可能 static 未更新"
    print("  线上前端 chunk 含 digest,0) 整数渲染 OK（旧构建为 digest,1)）")

    print("\n✅ 线上验证通过：车头/挂车预估消化数量已为整数（10×0.25=2.5 → 3，四舍五入；既有与新增数据一致）。")
finally:
    print("=== [7] 清理临时项目 ===")
    cleanup(token)
    print("  清理完成，生产无残留业务数据")
