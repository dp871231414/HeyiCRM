"""账号路由：增删改查、批量导入、删除前引用检查。

**可见范围口径**：账号上的 `scope` 为必填项，必须人工选择四档之一
（本人 / 本部门 / 本部门及下属部门 / 全公司），不再支持「跟随角色默认」。
角色上仍保留一个默认档位，仅作为新建账号时的建议值，不参与实际取数判定。
"""
from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import SCOPES
from app.core.deps import get_user_perms, require_perm
from app.core.security import hash_password
from app.db.session import get_db
from app.models import MarketProject, MetricActual, OperationLog, Organization, Role, Task, User
from app.schemas.common import ImportResult
from app.schemas.user import StatusIn, UserCreate, UserOut, UserUpdate
from app.services.audit import write_log
from app.services.importer import (
    ACCOUNT_COLUMNS,
    ACCOUNT_OPTIONAL_COLUMNS,
    build_account_template,
    parse_rows,
    validate_account_rows,
)
from app.services.serializers import user_out

router = APIRouter(prefix="/users", tags=["账号"])
_SHEET_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=_SHEET_MIME,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def _next_user_id(db: Session) -> str:
    max_n = 0
    for uid in db.scalars(select(User.id)).all():
        m = re.fullmatch(r"U(\d+)", uid)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"U{max_n + 1:03d}"


def _validate_refs(db: Session, dept_id: str, role_id: str) -> None:
    if not db.get(Organization, dept_id):
        raise HTTPException(status_code=422, detail="所属部门不存在")
    if not db.get(Role, role_id):
        raise HTTPException(status_code=422, detail="角色不存在")


def _require_scope(scope: str | None) -> str:
    """数据可见范围必选：必须明确填入四档之一，不接受空值。"""
    if not scope or scope not in SCOPES:
        raise HTTPException(status_code=422, detail="请选择数据可见范围")
    return scope


@router.get("", response_model=list[UserOut])
def list_users(
    keyword: str = "",
    dept_id: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.view")),
):
    q = select(User).order_by(User.id)
    if dept_id:
        q = q.where(User.dept_id == dept_id)
    if status:
        q = q.where(User.status == status)
    rows = db.scalars(q).all()
    if keyword:
        rows = [u for u in rows if keyword in u.name or keyword in u.account]
    return [user_out(db, u) for u in rows]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    account = payload.account.strip()
    if db.scalar(select(User).where(User.account == account)):
        raise HTTPException(status_code=409, detail="账号已存在，请更换账号名")
    _validate_refs(db, payload.dept_id, payload.role_id)
    scope = _require_scope(payload.scope)
    uid = _next_user_id(db)
    new_user = User(
        id=uid,
        name=payload.name.strip(),
        account=account,
        password_hash=hash_password(payload.password),
        dept_id=payload.dept_id,
        role_id=payload.role_id,
        scope=scope,
        status=payload.status if payload.status in ("active", "disabled") else "active",
    )
    db.add(new_user)
    write_log(db, user, "create", "user", uid, {"account": account}, request)
    db.commit()
    db.refresh(new_user)
    return user_out(db, new_user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="账号不存在")
    _validate_refs(db, payload.dept_id, payload.role_id)
    target.name = payload.name.strip()
    target.dept_id = payload.dept_id
    target.role_id = payload.role_id
    # 数据可见范围必选：不允许再回退到「跟随角色默认」
    target.scope = _require_scope(payload.scope)
    target.status = payload.status if payload.status in ("active", "disabled") else target.status
    if payload.password:
        target.password_hash = hash_password(payload.password)
    write_log(db, user, "update", "user", user_id, {"name": target.name, "scope": target.scope}, request)
    db.commit()
    db.refresh(target)
    return user_out(db, target)


@router.post("/{user_id}/status", response_model=UserOut)
def set_status(
    user_id: str,
    payload: StatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.edit")),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="账号不存在")
    if payload.status not in ("active", "disabled"):
        raise HTTPException(status_code=422, detail="状态取值非法")
    if target.id == user.id and payload.status == "disabled":
        raise HTTPException(status_code=409, detail="不能停用当前登录账号")
    target.status = payload.status
    write_log(db, user, "status", "user", user_id, {"status": payload.status}, request)
    db.commit()
    db.refresh(target)
    return user_out(db, target)


# ------------------------------------------------------------------ 批量导入


@router.get("/import/template")
def account_template(db: Session = Depends(get_db), user: User = Depends(require_perm("account.import"))):
    """账号批量导入标准模板（部门 / 角色 / 范围 / 状态均带下拉校验）。"""
    return _xlsx(build_account_template(db), "账号批量导入标准模板.xlsx")


@router.post("/import", response_model=ImportResult)
async def account_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.import")),
):
    raw = await file.read()
    if len(raw) > settings.import_max_mb * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"文件不能超过 {settings.import_max_mb}MB")
    try:
        rows = parse_rows(raw, ACCOUNT_COLUMNS, settings.import_max_rows, optional=ACCOUNT_OPTIONAL_COLUMNS)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=422, detail="未读取到任何数据行")
    valid, errors = validate_account_rows(db, rows)
    if errors:
        return {"imported": 0, "errors": errors}
    created: list[str] = []
    for r in valid:
        uid = _next_user_id(db)
        db.add(
            User(
                id=uid,
                name=r["name"],
                account=r["account"],
                password_hash=hash_password(r["password"]),
                dept_id=r["deptId"],
                role_id=r["roleId"],
                scope=r["scope"],
                status=r["status"],
            )
        )
        # 立刻 flush：下一行要基于已写入的 ID 继续编号，否则会撞主键
        db.flush()
        created.append(uid)
        write_log(db, user, "create", "user", uid, {"account": r["account"], "via": "import"}, request)
    db.commit()
    return {"imported": len(created), "errors": []}


# ------------------------------------------------------------------ 删除


# 「被引用选择的填写项」：这些字段是人工从已有账号里挑出来的，一旦删除该账号，
# 历史数据里的名字就会变成悬空引用，因此都算作删除阻断项。
_ACCOUNT_REF_LABELS = [
    ("taskCreated", "创建了 {n} 条任务"),
    ("projectCreated", "创建了 {n} 个市场项目"),
    ("metricCreated", "创建了 {n} 个指标"),
    ("taskOwner", "被 {n} 条任务选为责任人"),
    ("projectOwner", "被 {n} 个市场项目选为负责人"),
    ("orgHead", "被 {n} 个部门选为负责人"),
]


def _account_refs(db: Session, target: User) -> dict:
    """统计账号在各业务表中的引用数。"""
    return {
        "taskCreated": db.scalar(select(func.count()).select_from(Task).where(Task.created_by == target.id)) or 0,
        "projectCreated": db.scalar(
            select(func.count()).select_from(MarketProject).where(MarketProject.created_by == target.id)
        )
        or 0,
        "metricCreated": db.scalar(
            select(func.count()).select_from(MetricActual).where(MetricActual.created_by == target.id)
        )
        or 0,
        "taskOwner": db.scalar(select(func.count()).select_from(Task).where(Task.owner == target.name)) or 0,
        "projectOwner": db.scalar(
            select(func.count()).select_from(MarketProject).where(MarketProject.owner == target.name)
        )
        or 0,
        "orgHead": db.scalar(
            select(func.count()).select_from(Organization).where(Organization.head == target.name)
        )
        or 0,
    }


@router.get("/{user_id}/impact")
def account_impact(user_id: str, db: Session = Depends(get_db), user: User = Depends(require_perm("account.view"))):
    """删除前的影响预检：返回该账号在各处的引用数，供确认弹窗展示。"""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="账号不存在")
    refs = _account_refs(db, target)
    refs["self"] = target.id == user.id
    return refs


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("account.delete")),
):
    """删除账号 · 仅当未被任何数据引用时允许。"""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="账号不存在")
    if target.id == user.id:
        raise HTTPException(status_code=409, detail="不能删除当前登录账号")

    refs = _account_refs(db, target)
    blocks = [tpl.format(n=refs[key]) for key, tpl in _ACCOUNT_REF_LABELS if refs.get(key)]
    if blocks:
        raise HTTPException(status_code=409, detail="该账号已被引用，不允许删除：" + "；".join(blocks))

    # 兜底：若该账号是最后一个仍具备账号管理权限的启用账号，删除会导致系统无法再管理账号
    admin_perms = {"account.edit", "account.role", "account.delete"}
    others = db.scalars(select(User).where(User.id != target.id, User.status == "active")).all()
    rest_admins = [u for u in others if admin_perms & set(get_user_perms(db, u))]
    my_perms = set(get_user_perms(db, target))
    if (admin_perms & my_perms) and not rest_admins:
        raise HTTPException(status_code=409, detail="该账号是最后一个具备账号管理权限的启用账号，不允许删除")

    # 审计日志保留：解除引用而不是级联删除
    db.execute(update(OperationLog).where(OperationLog.user_id == target.id).values(user_id=None))
    db.delete(target)
    write_log(db, user, "delete", "user", user_id, {"account": target.account}, request)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": user_id}}
