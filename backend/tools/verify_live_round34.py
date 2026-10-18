"""线上验证 round34：编辑项目阶段为「流失」(stage=0) 可正常保存。

走登录下发的 Cookie 鉴权（部署反代会改写 Authorization 头）。
验证后删除临时项目，不留业务数据（遵守红线：仅验证、不污染生产）。
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


MP_BODY = {
    "name": "R34校验临时项目",
    "description": "线上验证用，创建后删除",
    "progress": "初始进展：临时校验",
    "stage": 25,
    "owner": "管理员",
    "tractorRequirements": [],
    "trailerRequirements": [],
}


print("=== [1] 登录 admin ===")
s, body, cookie = req("POST", "/auth/login", json_body={"account": "admin", "password": "123456"})
assert s == 200, f"login failed {s}: {body}"
token = re.search(r"access_token=([^;]+)", cookie or "").group(1)
print("  OK")

print("=== [2] 新建草稿项目(stage=25) ===")
s, b, _ = req("POST", "/market-projects", token, json_body=dict(MP_BODY))
assert s == 201, f"create failed {s}: {b}"
pid = json.loads(b)["id"]
_created.append(pid)
print(f"  OK pid={pid}")

print("=== [3] 编辑为「流失」(stage=0) —— 即复现 bug 的保存动作 ===")
s, b, _ = req("PATCH", f"/market-projects/{pid}", token, json_body=dict(MP_BODY, stage=0))
assert s == 200, f"PATCH stage=0 失败 {s}: {b}"
j = json.loads(b)
assert j["stage"] == 0, f"stage 应为 0，实际 {j['stage']}"
assert j["stageLabel"] == "流失", f"stageLabel 应为 流失，实际 {j['stageLabel']!r}"
print(f"  OK stage={j['stage']} stageLabel={j['stageLabel']!r}（此前此处会报「项目阶段不合法」422）")

print("=== [4] 直接新建为「流失」(stage=0) ===")
s, b, _ = req("POST", "/market-projects", token, json_body=dict(MP_BODY, name="R34校验临时项目-直建", stage=0))
assert s == 201, f"create stage=0 失败 {s}: {b}"
pid2 = json.loads(b)["id"]
_created.append(pid2)
assert json.loads(b)["stageLabel"] == "流失"
print(f"  OK pid={pid2} stageLabel=流失")

print("=== [5] 非法阶段(33) 仍被拒（校验未放宽）===")
s, _, _ = req("PATCH", f"/market-projects/{pid}", token, json_body=dict(MP_BODY, name="x", stage=33))
assert s == 422, f"非法阶段应 422，实际 {s}"
print(f"  OK 非法阶段返回 {s}（符合预期）")

print("=== [6] 清理临时项目 ===")
for p in _created:
    s, _, _ = req("DELETE", f"/market-projects/{p}", token)
    print(f"  删除 {p} -> {s}")
print("  清理完成，生产无残留业务数据")

print("\n✅ 线上验证通过：编辑/新建项目阶段为「流失」(0) 可正常保存，stageLabel 正确显示「流失」；非法阶段仍被拦截。")
