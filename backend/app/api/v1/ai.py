"""AI 能力路由：经营驾驶舱的「AI 经营点评」。

模型调用放在服务端，Key 不下发前端；前端拿不到 Key 就无法盗用。
调用失败统一返回 502，前端据此回退到云服务通道，再失败则展示规则化分析。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.deps import require_perm
from app.models import User
from app.services import ai as ai_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI 能力"])


class InsightIn(BaseModel):
    context: str = Field("", description="由前端汇总的经营数据上下文")


class InsightOut(BaseModel):
    text: str
    source: str = "custom"


@router.post("/insight", response_model=InsightOut)
def insight(payload: InsightIn, user: User = Depends(require_perm("dashboard.view"))):
    try:
        text = ai_svc.build_insight(payload.context)
    except ai_svc.AIServiceError as exc:
        logger.warning("AI 点评失败：%s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"text": text, "source": "custom"}


@router.get("/status")
def status(user: User = Depends(require_perm("dashboard.view"))):
    """告知前端自定义模型是否可用，便于界面提示与排障。

    只暴露「是否配置/模型名」，绝不返回 Key 或 base_url。
    """
    return {
        "customEnabled": settings.ai_enabled,
        "model": settings.ai_model if settings.ai_enabled else "",
    }
