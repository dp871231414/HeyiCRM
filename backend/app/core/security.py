"""密码哈希与 JWT 令牌。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

_BCRYPT_MAX_BYTES = 72


def _encode(password: str) -> bytes:
    # bcrypt 仅取前 72 字节，先截断避免抛错
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
