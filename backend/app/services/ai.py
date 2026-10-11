"""自定义大模型调用（OpenAI 兼容协议）。

设计要点：
- API Key 只从服务端环境变量读取，**绝不**出现在任何响应里，前端也拿不到。
- 非流式聚合调用：驾驶舱点评只需一段短文本，流式对后端没有收益，
  反而增加 SSE 解析与中断处理的复杂度。实测自定义模型 1~2 秒即可返回。
- 统一超时（默认 30s）与错误归一化，调用方只需处理一种异常类型。
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# 与前端 SYSTEM_PROMPT 保持一致，避免两端措辞漂移
SYSTEM_PROMPT = (
    "你是「合一重卡生态经营看板」的经营分析助手。请基于输入的经营数据，"
    "用简洁、客观的中文给出 2~3 句经营点评：先点出最值得关注的一项，"
    "再给出一条可执行的建议。只依据输入数据，不要编造数字。"
)

MAX_CONTEXT_CHARS = 4000


class AIServiceError(RuntimeError):
    """对外统一的调用失败异常，消息已脱敏（不含 Key、不含上游原始报文）。"""


def _make_client() -> httpx.Client:
    """构造发往模型服务的客户端。

    单独抽出来是为了让测试能替换这一处，而不影响框架自身对 httpx 的使用。
    """
    return httpx.Client(timeout=settings.ai_timeout)


def build_insight(context: str) -> str:
    """调用自定义模型生成经营点评，返回纯文本。

    失败时抛 AIServiceError，由路由层转成 502，前端据此回退云服务。
    """
    if not settings.ai_enabled:
        raise AIServiceError("未配置自定义模型")

    context = (context or "").strip()[:MAX_CONTEXT_CHARS]
    if not context:
        raise AIServiceError("经营数据上下文为空")

    url = settings.ai_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        "stream": False,
        "temperature": 1,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.ai_api_key}",
    }

    try:
        with _make_client() as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise AIServiceError(f"模型响应超时（>{settings.ai_timeout:.0f}s）") from exc
    except httpx.HTTPError as exc:
        raise AIServiceError("模型服务网络异常") from exc

    if resp.status_code != 200:
        # 只记录状态码，不回传上游报文（可能含敏感信息）
        logger.warning("AI 服务返回非 200：status=%s model=%s", resp.status_code, settings.ai_model)
        raise AIServiceError(f"模型服务返回 {resp.status_code}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AIServiceError("模型响应格式异常") from exc

    content = (content or "").strip()
    if not content:
        raise AIServiceError("模型返回内容为空")
    return content
