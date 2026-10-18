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

    from sqlalchemy import text

    # 迁移：主任务 -> 任务组（在 create_all 之前执行，避免新建空 task_group 与旧 main_task 共存）
    with engine.begin() as conn:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "main_task" in tables:
            if "task_group" in tables:
                conn.execute(text("DROP TABLE task_group"))
            conn.execute(text("ALTER TABLE main_task RENAME TO task_group"))
        if "task" in tables:
            tcols = {r[1] for r in conn.execute(text("PRAGMA table_info(task)")).fetchall()}
            if "main_task_id" in tcols and "task_group_id" not in tcols:
                conn.execute(text("ALTER TABLE task RENAME COLUMN main_task_id TO task_group_id"))

    # 迁移：任务组名称去「库级唯一约束」——唯一性改为「名称 + 责任人」联合（由接口层校验）。
    # 老库 task_group.name 上可能残留 autoindex，需移除，否则同名不同责任人的任务组无法共存。
    with engine.begin() as conn:
        tg = conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='task_group'")
        ).fetchone()
        if tg:
            idxs = conn.execute(text("PRAGMA index_list(task_group)")).fetchall()
            for row in idxs:
                # PRAGMA index_list 列：seq, name, unique, origin, partial
                idx_name, is_unique = row[1], row[2]
                if not is_unique:
                    continue
                cols = conn.execute(text(f"PRAGMA index_info({idx_name})")).fetchall()
                col_names = {c[2] for c in cols}
                if col_names == {"name"}:
                    try:
                        conn.execute(text(f"ALTER TABLE task_group DROP CONSTRAINT {idx_name}"))
                        logger.info("已移除 task_group.name 库级唯一约束（%s）", idx_name)
                    except Exception as exc:  # pragma: no cover - 极旧版本无 DROP CONSTRAINT
                        logger.warning("DROP CONSTRAINT 失败，退化为整表重建：%s", exc)
                        conn.execute(
                            text(
                                "CREATE TABLE task_group_new ("
                                "id VARCHAR(32) PRIMARY KEY, name VARCHAR(128) NOT NULL, "
                                "created_by VARCHAR(16), created_at TIMESTAMP, owner_id VARCHAR(16), "
                                "dept_id VARCHAR(16), updated_at TIMESTAMP, is_system BOOLEAN)"
                            )
                        )
                        conn.execute(
                            text(
                                "INSERT INTO task_group_new "
                                "(id, name, created_by, created_at, owner_id, dept_id, updated_at, is_system) "
                                "SELECT id, name, created_by, created_at, owner_id, dept_id, updated_at, is_system "
                                "FROM task_group"
                            )
                        )
                        conn.execute(text("DROP TABLE task_group"))
                        conn.execute(text("ALTER TABLE task_group_new RENAME TO task_group"))
                        logger.info("已通过整表重建移除 task_group.name 库级唯一约束")

    Base.metadata.create_all(bind=engine)
    logger.info("数据库表已就绪")

    with engine.begin() as conn:
        # market_project 补列（原逻辑保留）
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(market_project)")).fetchall()}
        if "owner_dept_id" not in existing:
            conn.execute(text("ALTER TABLE market_project ADD COLUMN owner_dept_id VARCHAR(16)"))
            logger.info("已为 market_project 补列 owner_dept_id")
        if "progress" not in existing:
            conn.execute(text("ALTER TABLE market_project ADD COLUMN progress TEXT NOT NULL DEFAULT ''"))
            logger.info("已为 market_project 补列 progress")
        # task_group 缺失字段补 ALTER（责任人/责任部门/更新时间），老库兼容
        tg_exists = conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='task_group'")
        ).fetchone()
        if tg_exists:
            gcols = {r[1] for r in conn.execute(text("PRAGMA table_info(task_group)")).fetchall()}
            for col, ddl in [("owner_id", "VARCHAR(16)"), ("dept_id", "VARCHAR(16)"), ("updated_at", "TIMESTAMP")]:
                if col not in gcols:
                    conn.execute(text(f"ALTER TABLE task_group ADD COLUMN {col} {ddl}"))
                    logger.info(f"已为 task_group 补列 {col}")
        # user.preferences：用户级偏好（行高等），老库补 ALTER，默认值 '{}'
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(\"user\")")).fetchall()}
        if "preferences" not in existing:
            conn.execute(text("ALTER TABLE \"user\" ADD COLUMN preferences TEXT NOT NULL DEFAULT '{}'"))
            logger.info("已为 user 补列 preferences")


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
