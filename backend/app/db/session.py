"""数据库会话与引擎。

生产使用 PostgreSQL；测试可切换到 SQLite（连接串由环境变量 DATABASE_URL 控制）。
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

if settings.is_sqlite:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
