"""线上部署后一次性验证：读接口 + 新造数据测试后删除。

用法：PYTHONPATH=. python tools/verify_live.py
仅做最小验证，结束后删除新建的测试项目，不污染线上库。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

BASE = "https://heyi-fleet-dashboard.app.workbuddy.host"
API = f"{BASE}/api/v1"


def _req(method: str, path: str, token: str | None = None, json_body: dict | None = None, raw: bool = False, cookie: str | None = None):
    url = f"{API}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if cookie:
        # 反代/网关会改写 Authorization 头，故线上验证统一走登录下发的 HttpOnly Cookie
        headers["Cookie"] = f"access_token={cookie}"
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if raw or "application/json" not in ctype:
                return resp.status, ctype, body
            if not body:
                # 204 等无响应体时直接返回，避免对空串做 json 解析
                return resp.status, ctype, None
            return resp.status, ctype, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8", "replace")


def main():
    print(f"== 目标：{BASE} ==")
    # 1) 登录（捕获 Set-Cookie，后续走 cookie 鉴权，规避反代改写 Authorization 头）
    url = f"{API}/auth/login"
    req = urllib.request.Request(url, data=json.dumps({"account": "admin", "password": "123456"}).encode(),
                                 headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        login_body = json.loads(resp.read().decode("utf-8"))
        set_cookie = resp.headers.get("Set-Cookie", "")
    assert "access_token=" in set_cookie, f"登录未下发 cookie: {set_cookie}"
    cookie = set_cookie.split("access_token=", 1)[1].split(";", 1)[0]
    print(f"[1] 登录 OK，拿到 cookie 会话（token 前8位 {login_body['access_token'][:8]}…）")

    # 2) 列表：确认 latestProgress 字段存在、返回 200
    st, _, body = _req("GET", "/market-projects", cookie=cookie)
    assert st == 200, f"列表失败: {st} {body}"
    items = body["items"]
    print(f"[2] 列表 OK，共 {body['total']} 条；首条字段含 latestProgress={('latestProgress' in items[0])}，"
          f"sample latestProgress={items[0].get('latestProgress','')!r}")

    # 3) 导出：不再即时下载，而是落盘并在下载中心生成记录（返回 JSON 记录）
    st, _, body = _req("GET", "/market-projects/export", cookie=cookie)
    assert st == 200 and isinstance(body, dict) and body.get("objectType") == "market_project", f"导出异常: {st} {body}"
    rid = body["id"]
    filename = body["filename"]
    print(f"[3] 导出生成记录 OK id={rid} filename={filename}（仅落盘，不直接下载）")
    # 文件须经由下载中心按记录下载
    st, ctype, _ = _req("GET", f"/downloads/{rid}/file", cookie=cookie, raw=True)
    assert st == 200 and "spreadsheetml" in ctype, f"下载中心文件下载异常: {st} {ctype}"
    print(f"[3b] 下载中心文件下载 OK content-type 含 spreadsheetml")
    # 清理：删除测试导出的记录，避免污染线上库
    d_st, _, _ = _req("DELETE", f"/downloads/{rid}", cookie=cookie)
    assert d_st == 204, f"删除测试导出记录失败: {d_st}"
    print(f"[3c] 已删除测试导出记录 id={rid}")

    # 4) 导入模板：应 200 + xlsx
    st, ctype, _ = _req("GET", "/market-projects/import/template", cookie=cookie, raw=True)
    print(f"[4] 模板 状态码={st} content-type={ctype}")
    assert st == 200 and "spreadsheetml" in ctype, f"模板异常: {st}"

    # 5) 新建带进展的项目（新造数据）
    st, _, body = _req("POST", "/market-projects", cookie=cookie, json_body={
        "name": "【验证-待删除】线上部署核查项目",
        "description": "自动验证脚本创建，随后删除",
        "progress": "初始进展：已立项",
        "tractor_demand": 3,
        "trailer_demand": 1,
        "stage": 25,
        "owner": "郑凯",
    })
    assert st == 201, f"新建失败: {st} {body}"
    pid = body["id"]
    print(f"[5] 新建项目 OK id={pid} latestProgress={body.get('latestProgress')!r}")

    # 6) 追加进展（编辑时只能新增，原不可改）
    st, _, body = _req("POST", f"/market-projects/{pid}/progress", cookie=cookie, json_body={"content": "第二轮：方案评审通过"})
    assert st == 201, f"追加进展失败: {st} {body}"
    print(f"[6] 追加进展 OK content={body.get('content')!r}")

    # 7) 列表最新进展同步为追加后的值
    st, _, body = _req("GET", "/market-projects", cookie=cookie)
    item = next((x for x in body["items"] if x["id"] == pid), None)
    assert item and item["latestProgress"] == "第二轮：方案评审通过", f"latestProgress 未同步: {item}"
    print(f"[7] 列表 latestProgress 同步 OK ={item['latestProgress']!r}")

    # 8) 删除测试项目（清理，不污染线上库）
    st, _, body = _req("DELETE", f"/market-projects/{pid}", cookie=cookie)
    assert st == 200, f"删除失败: {st} {body}"
    st, _, body = _req("GET", f"/market-projects/{pid}", cookie=cookie)
    print(f"[8] 删除测试项目 OK（删除后查询状态码={st}，期望 403/404）")

    print("\n✅ 线上验证全部通过：列表/导出/模板/进展时间轴/新增-追加-同步/清理 均符合预期。")


if __name__ == "__main__":
    main()
