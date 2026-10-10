"""元数据路由 · 供任意已登录用户使用的基础字典（不含统计与敏感信息）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ORG_TYPE_PROJECT
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Organization, User

router = APIRouter(prefix="/meta", tags=["元数据"])


@router.get("/orgs")
def org_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """组织下拉选项：全公司 + 部门层级（不含项目公司）。"""
    rows = list(db.scalars(select(Organization).order_by(Organization.sort_order, Organization.id)).all())
    by_parent: dict[str | None, list[Organization]] = {}
    for o in rows:
        by_parent.setdefault(o.parent_id, []).append(o)

    out: list[dict] = []

    def walk(parent_id: str | None, depth: int) -> None:
        for o in by_parent.get(parent_id, []):
            if o.type == ORG_TYPE_PROJECT:
                continue
            out.append({"id": o.id, "name": o.name, "type": o.type, "parentId": o.parent_id, "head": o.head, "depth": depth})
            walk(o.id, depth + 1)

    walk(None, 0)
    return out


@router.get("/owners")
def owner_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """责任人候选：系统内启用状态的账号姓名。"""
    rows = db.scalars(select(User).where(User.status == "active").order_by(User.id)).all()
    return [{"id": u.id, "name": u.name, "deptId": u.dept_id} for u in rows]
