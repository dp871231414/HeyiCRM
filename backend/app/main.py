"""FastAPI 应用入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """按需自动建表（开发/首次部署便利）；生产建议以 Alembic 迁移为准。"""
    from app.db.base import Base
    from app.db.session import engine
    import app.models  # noqa: F401  注册模型

    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已就绪")
    yield


app = FastAPI(
    title=settings.app_name,
    description="合一重卡生态经营看板 · 前后端分离后端服务",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):  # pragma: no cover
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.env}
