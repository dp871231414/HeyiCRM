"""线上验证 Round 32：车辆需求分析模块（仅读，不写数据）。"""
import json
import re
import urllib.request

BASE = "https://heyi-fleet-dashboard.app.workbuddy.host"
API = f"{BASE}/api/v1"


def req(method, path, token=None, cookie=None, json_body=None):
    url = API + path if path.startswith("/") else path
    data = json.dumps(json_body).encode() if json_body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # 线上反代会改写 Authorization 头，须用登录下发的 HttpOnly Cookie 鉴权
    if cookie:
        headers["Cookie"] = cookie
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        set_cookie = resp.headers.get("Set-Cookie")
        body = resp.read().decode()
        return resp.status, body, set_cookie
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers.get("Set-Cookie")


def get_json(path, cookie):
    status, body, _ = req("GET", path, cookie=cookie)
    return status, json.loads(body) if body else None


print("=== [1] 登录 admin ===")
s, body, set_cookie = req("POST", "/auth/login", json_body={"account": "admin", "password": "123456"})
assert s == 200, f"login failed {s}: {body}"
# 取登录下发的 access_token cookie 用于后续请求
cookie = re.search(r"access_token=([^;]+)", set_cookie or "").group(1)
cookie = f"access_token={cookie}"
print("  OK 登录成功")

print("=== [2] 车辆需求分析接口 ===")
s, b = get_json("/dashboard/demand-analysis", cookie)
assert s == 200, f"demand-analysis failed {s}: {b}"
stages = b.get("stages", [])
assert stages, "stages 为空"
for st in stages:
    assert 0 <= st["prob"] <= 1, f"prob 越界 {st}"
print(f"  OK 接口 200，阶段数={len(stages)}，转化率后缀样品:")
for st in stages:
    print(f"     {st['label']} {round(st['prob']*100)}%")

print("=== [3] 车头/挂车结构 ===")
t = b["tractor"]
tr = b["trailer"]
assert "all" in t and "byStage" in t, "tractor 缺 all/byStage"
assert "all" in tr and "byStage" in tr, "trailer 缺 all/byStage"
# 校验挂车 all 每行含 总数量(qty) 与 预估消化(digest)，且 digest<=qty（转化率<=1）
for row in tr["all"]:
    assert "qty" in row and "digest" in row, f"trailer 行缺字段: {row}"
    assert row["digest"] <= row["qty"] + 1e-6, f"digest 越界 {row}"
# 校验 byStage 的 key 与 stages 一致（字符串 stage）
stage_keys = {str(st["stage"]) for st in stages}
assert set(tr["byStage"].keys()).issubset(stage_keys), "byStage key 异常"
print(f"  OK 车头组合={len(t['all'])}，挂车车型={len(tr['all'])}，byStage 键集 ⊂ 阶段集")

print("=== [4] 前端构建含新模块 ===")
html = urllib.request.urlopen(f"{BASE}/", timeout=30).read().decode()
# DashboardView 是懒加载块，不在 index.html 直接列出，而在入口 bundle 里以动态 import 引用
entry = re.search(r'src="(/assets/[^"]+\.js)"', html)
assert entry, "未找到入口 bundle"
entry_js = urllib.request.urlopen(f"{BASE}{entry.group(1)}", timeout=30).read().decode(errors="ignore")
m = re.search(r"DashboardView-([A-Za-z0-9_-]+)\.js", entry_js)
assert m, "入口 bundle 未引用 DashboardView 块"
dash_name = f"DashboardView-{m.group(1)}.js"
js = urllib.request.urlopen(f"{BASE}/assets/{dash_name}", timeout=30).read().decode(errors="ignore")
assert "车辆需求分析" in js, "前端缺「车辆需求分析」"
assert "预估消化数量" in js, "前端缺「预估消化数量」"
assert "按阶段筛选" in js, "前端缺「按阶段筛选」"
print(f"  OK 在线 {dash_name} 含「车辆需求分析 / 预估消化数量 / 按阶段筛选」")

print("\n✅ 线上验证全部通过：车辆需求分析模块已上线（车头×电池容量组合 + 挂车按车型含预估消化，阶段筛选标签带转化率后缀）。")
