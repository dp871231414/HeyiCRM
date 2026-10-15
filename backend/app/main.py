"""FastAPI 应用入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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

    # 兼容已上线但模型后续新增列的旧库：market_project.owner_dept_id 是后来补的字段，
    # 旧库（dev.db / 线上 app.db）建表时还没有它。这里在启动时为缺失列做一次 ALTER，
    # 避免查询该列报 "no such column"。全新库由 create_all 直接带列，跳过。
    from sqlalchemy import text

    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(market_project)")).fetchall()}
        if "owner_dept_id" not in existing:
            conn.execute(text("ALTER TABLE market_project ADD COLUMN owner_dept_id VARCHAR(16)"))
            logger.info("已为 market_project 补列 owner_dept_id")

        # task.main_task_id：本轮新增的「主任务」外键列，老库同样补 ALTER
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(task)")).fetchall()}
        if "main_task_id" not in existing:
            conn.execute(text("ALTER TABLE task ADD COLUMN main_task_id VARCHAR(32)"))
            logger.info("已为 task 补列 main_task_id")

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

# 传输压缩：JS / CSS / JSON 的体积可减少约 60%（原先 169KB 的主包原样传输）
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):  # pragma: no cover
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.env}


# ---------------------------------------------------------------------------
# 单容器托管：设置 STATIC_DIR 指向前端构建产物（dist）时，由后端直接托管 SPA，
# 实现「一个端口、同源」部署；不设置则保持前后端分离（由 Nginx 托管前端）。
# ---------------------------------------------------------------------------
_static_dir = Path(settings.static_dir).resolve() if settings.static_dir else None
if _static_dir and _static_dir.is_dir():

    class _HashedAssetFiles(StaticFiles):
        """构建产物按内容哈希命名（如 index--tnUtUiB.js），内容变则文件名变，可长期强缓存。"""

        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            if response.status_code == 200:
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

    _assets = _static_dir / "assets"
    if _assets.is_dir():
        app.mount("/assets", _HashedAssetFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """静态文件优先，其余路径回退到 index.html（前端 history 路由）。"""
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = (_static_dir / full_path).resolve()
        if full_path and candidate.is_file() and _static_dir in candidate.parents:
            return FileResponse(str(candidate), headers={"Cache-Control": "public, max-age=3600"})
        # index.html 不做缓存：它内部引用带哈希的资源名，必须随发布及时更新
        return FileResponse(str(_static_dir / "index.html"), headers={"Cache-Control": "no-cache"})

    logger.info("已启用单容器托管，静态目录：%s", _static_dir)
