"""AI 点评接口测试。

不真实调用外部模型：通过替换 `app.services.ai._make_client` 精确打桩，
既不依赖网络与真实额度，也不会影响 TestClient 自身对 httpx 的使用。

重点验证：鉴权、权限、脱敏（不回传 Key / 上游报文）、错误归一化。
"""
from __future__ import annotations

import contextlib
import json

import httpx
import pytest

from app.config import settings
from app.models import Role
from app.services import ai as ai_svc
from tests.conftest import login

SECRET = "sk-secret-value-should-never-leak"
UPSTREAM = "https://example-llm.test"


class Recorder:
    """记录发往上游的请求，并按预设返回响应（或抛出异常）。"""

    def __init__(self, payload: dict | None = None, status_code: int = 200, raises: Exception | None = None):
        self.payload = payload if payload is not None else {"choices": [{"message": {"content": "占位"}}]}
        self.status_code = status_code
        self.raises = raises
        self.calls: list[dict] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(
                {
                    "url": str(request.url),
                    "headers": dict(request.headers),
                    "body": json.loads(request.content.decode()) if request.content else {},
                }
            )
            if self.raises is not None:
                raise self.raises
            return httpx.Response(self.status_code, json=self.payload)

        return httpx.MockTransport(handler)

    @property
    def last(self) -> dict:
        assert self.calls, "未捕获到任何上游请求"
        return self.calls[-1]


def patch_upstream(monkeypatch, rec: Recorder | None = None, **kwargs) -> Recorder:
    """替换 service 内部的 client 构造，返回记录器。"""
    recorder = rec or Recorder(**kwargs)
    monkeypatch.setattr(ai_svc, "_make_client", lambda: httpx.Client(transport=recorder.transport()))
    return recorder


def ok_text(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


@pytest.fixture
def ai_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ai_base_url", UPSTREAM, raising=False)
    monkeypatch.setattr(settings, "ai_api_key", SECRET, raising=False)
    monkeypatch.setattr(settings, "ai_model", "test-model", raising=False)
    monkeypatch.setattr(settings, "ai_timeout", 30.0, raising=False)


@pytest.fixture(autouse=True)
def _isolate_cookies(client):
    """每个用例后清掉 Cookie。

    后端鉴权是「Authorization 头优先、Cookie 兜底」，TestClient 会保留登录 Cookie；
    不清理的话，后续「匿名」用例会被上一个登录态污染。
    """
    yield
    client.cookies.clear()


# ---------------------------------------------------------------- 配置与脱敏


def test_ai_status_reports_enabled(client, admin_headers, ai_enabled):
    resp = client.get("/api/v1/ai/status", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == {"customEnabled": True, "model": "test-model"}


def test_ai_status_never_exposes_key_or_url(client, admin_headers, ai_enabled):
    """状态接口不得泄露 Key 与上游地址。"""
    body = client.get("/api/v1/ai/status", headers=admin_headers).text
    assert SECRET not in body
    assert UPSTREAM not in body


def test_ai_status_disabled_when_unconfigured(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "ai_base_url", "", raising=False)
    monkeypatch.setattr(settings, "ai_api_key", "", raising=False)
    monkeypatch.setattr(settings, "ai_model", "", raising=False)
    assert client.get("/api/v1/ai/status", headers=admin_headers).json() == {"customEnabled": False, "model": ""}


# ---------------------------------------------------------------- 鉴权与权限


def test_insight_requires_login(client, ai_enabled):
    client.cookies.clear()
    assert client.post("/api/v1/ai/insight", json={"context": "x"}).status_code == 401


def test_insight_rejects_role_without_dashboard_view(client, ai_enabled):
    """无 dashboard.view 的角色不得调用，避免模型额度被无谓消耗。"""
    from app.db.session import SessionLocal

    headers, _ = login(client, "zhengkai")
    with SessionLocal() as db:
        role = db.get(Role, "member")
        original = list(role.permissions or [])
        role.permissions = [p for p in original if p != "dashboard.view"]
        db.commit()
        try:
            resp = client.post("/api/v1/ai/insight", json={"context": "x"}, headers=headers)
            assert resp.status_code == 403
        finally:
            role.permissions = original
            db.commit()


def test_member_can_call_insight(client, member_headers, ai_enabled, monkeypatch):
    """成员角色含 dashboard.view，应可调用（与驾驶舱数据可见口径一致）。"""
    patch_upstream(monkeypatch, payload=ok_text("成员也能看到点评"))
    resp = client.post("/api/v1/ai/insight", json={"context": "x"}, headers=member_headers)
    assert resp.status_code == 200
    assert resp.json()["text"] == "成员也能看到点评"


# ---------------------------------------------------------------- 正常路径


def test_insight_returns_text_and_calls_configured_upstream(client, admin_headers, ai_enabled, monkeypatch):
    rec = patch_upstream(monkeypatch, payload=ok_text("运力收入缺口最大，建议专项分析。"))
    resp = client.post("/api/v1/ai/insight", json={"context": "达成率 84.2%"}, headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json() == {"text": "运力收入缺口最大，建议专项分析。", "source": "custom"}
    assert rec.last["url"] == f"{UPSTREAM}/chat/completions"
    assert rec.last["headers"]["authorization"] == f"Bearer {SECRET}"
    assert rec.last["body"]["model"] == "test-model"
    assert rec.last["body"]["messages"][0]["role"] == "system"
    assert rec.last["body"]["messages"][1]["content"] == "达成率 84.2%"


# ---------------------------------------------------------------- 失败路径


@pytest.mark.parametrize(
    "status_code,payload,expect",
    [
        (429, {"error": f"rate limited, key {SECRET}"}, "模型服务返回 429"),
        (401, {"error": f"invalid api key {SECRET}"}, "模型服务返回 401"),
        (500, {"error": "boom"}, "模型服务返回 500"),
        (200, {"choices": []}, "模型响应格式异常"),
        (200, {"unexpected": "shape"}, "模型响应格式异常"),
        (200, {"choices": [{"message": {"content": "   "}}]}, "模型返回内容为空"),
    ],
)
def test_upstream_errors_are_normalized_and_sanitized(
    client, admin_headers, ai_enabled, monkeypatch, status_code, payload, expect
):
    patch_upstream(monkeypatch, payload=payload, status_code=status_code)
    resp = client.post("/api/v1/ai/insight", json={"context": "x"}, headers=admin_headers)

    assert resp.status_code == 502
    assert resp.json()["detail"] == expect
    # 上游报文（可能含 Key）绝不回传前端
    assert SECRET not in resp.text


def test_empty_context_rejected(client, admin_headers, ai_enabled, monkeypatch):
    rec = patch_upstream(monkeypatch, payload=ok_text("x"))
    resp = client.post("/api/v1/ai/insight", json={"context": "   "}, headers=admin_headers)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "经营数据上下文为空"
    assert not rec.calls, "空上下文不应触发上游请求"


def test_timeout_is_reported(client, admin_headers, ai_enabled, monkeypatch):
    patch_upstream(monkeypatch, raises=httpx.ReadTimeout("too slow"))
    resp = client.post("/api/v1/ai/insight", json={"context": "x"}, headers=admin_headers)
    assert resp.status_code == 502
    assert "超时" in resp.json()["detail"]


def test_network_error_is_reported(client, admin_headers, ai_enabled, monkeypatch):
    patch_upstream(monkeypatch, raises=httpx.ConnectError("refused"))
    resp = client.post("/api/v1/ai/insight", json={"context": "x"}, headers=admin_headers)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "模型服务网络异常"


def test_not_configured_returns_502(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "ai_base_url", "", raising=False)
    monkeypatch.setattr(settings, "ai_api_key", "", raising=False)
    monkeypatch.setattr(settings, "ai_model", "", raising=False)
    resp = client.post("/api/v1/ai/insight", json={"context": "x"}, headers=admin_headers)
    assert resp.status_code == 502
    assert resp.json()["detail"] == "未配置自定义模型"


# ---------------------------------------------------------------- service 层


def test_service_truncates_overlong_context(monkeypatch, ai_enabled):
    rec = patch_upstream(monkeypatch, payload=ok_text("ok"))
    ai_svc.build_insight("A" * 9999)
    assert len(rec.last["body"]["messages"][1]["content"]) == ai_svc.MAX_CONTEXT_CHARS


def test_service_strips_whitespace(monkeypatch, ai_enabled):
    patch_upstream(monkeypatch, payload=ok_text("  结论明确  \n"))
    assert ai_svc.build_insight("ctx") == "结论明确"


def test_make_client_uses_configured_timeout(monkeypatch, ai_enabled):
    monkeypatch.setattr(settings, "ai_timeout", 12.5, raising=False)
    with contextlib.closing(ai_svc._make_client()) as c:
        assert c.timeout.read == 12.5
