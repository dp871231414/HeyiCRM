"""应用配置 · 全部走环境变量，代码零硬编码。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "合一重卡生态经营看板"
    env: str = "production"
    debug: bool = False

    # 数据库
    database_url: str = "sqlite:///./dev.db"
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # 鉴权
    jwt_secret: str = "change-me-to-a-random-32+char-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    cookie_secure: bool = False

    # 业务口径（留空则按服务器当天推导；显式设置可固定演示口径）
    current_period: str | None = None
    data_as_of: str | None = None

    # 跨域
    cors_origins: str = ""

    # 导入
    import_max_mb: int = 5
    import_max_rows: int = 2000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
