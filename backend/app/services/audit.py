"""操作日志留痕。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.deps import get_client_ip
from app.models import OperationLog, User


def write_log(
    db: Session,
    user: User | None,
    action: str,
    target_type: str = "",
    target_id: str = "",
    detail: dict | None = None,
    request: Request | None = None,
) -> None:
    db.add(
        OperationLog(
            user_id=user.id if user else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id or ""),
            detail=detail or {},
            ip=get_client_ip(request) if request else None,
        )
    )
