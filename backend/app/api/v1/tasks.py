"""任务路由：增删改查、部门完成度聚合、导入导出。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ORG_TYPE_TEAM
from app.core.deps import get_user_perms, require_perm
from app.db.session import get_db
from app.models import Organization, Task, User
from app.schemas.common import ImportResult
from app.schemas.task import DeptTaskStat, TaskCreate, TaskListOut, TaskOut, TaskUpdate
from app.services import scope as scope_svc
from app.services.achievement import reference_date, task_to_dict
from app.services.audit import write_log
from app.services.importer import (
    TASK_COLUMNS,
    TASK_OPTIONAL_COLUMNS,
    build_task_template,
    export_tasks,
    import_tasks,
    next_task_id,
    parse_rows,
    validate_task_rows,
)
from app.services.serializers import org_name
from urllib.parse import quote

router = APIRouter(prefix="/tasks", tags=["任务"])

_SHEET_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=_SHEET_MIME,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# 分页上限：分组视图需一次取全量以做「每组独立分页」，故上限放宽但仍设护栏
DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 2000


def _status_condition(status: str, today: date):
    """把任务状态判定下推到 SQL —— 与 services.achievement.task_health 保持同一套语义。

    否则会出现「分页在数据库层、过滤在 Python 层」，页数与总数对不上。
    """
    done = and_(Task.target > 0, Task.done >= Task.target)
    not_done = ~done
    if status == "done":
        return done
    if status == "overdue":
        return and_(not_done, Task.end_date < today)
    if status == "due_soon":
        # 异常任务在未逾期时被归为「异常」，故这里要排除异常
        return and_(not_done, Task.end_date == today, Task.abnormal.is_(False))
    if status == "normal":
        return and_(not_done, Task.end_date > today, Task.abnormal.is_(False))
    if status == "risk":
        return and_(Task.abnormal.is_(True), not_done, Task.end_date >= today)
    return None


def _visible_query(db: Session, user: User):
    q = select(Task)
    cond = scope_svc.visible_task_filter(db, user)
    if cond is not None:
        q = q.where(cond)
    return q


def _task_or_404(db: Session, user: User, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    cond = scope_svc.visible_task_filter(db, user)
    if cond is not None:
        visible = db.scalar(select(Task).where(Task.id == task_id, cond))
        if not visible:
            raise HTTPException(status_code=403, detail="无权访问该任务")
    return task


def _enrich(db: Session, items: list[dict]) -> list[dict]:
    """批量补齐展示用名称：责任部门名 + 创建人名。

    创建人由 created_by（用户 ID）解析为姓名，供列表与导出直接展示；
    组织名与用户名都做去重缓存，避免逐条查询造成 N+1。
    """
    dept_names: dict[str, str] = {}
    creator_ids = {str(it.get("createdById") or "") for it in items} - {""}
    creators: dict[str, str] = {}
    if creator_ids:
        creators = {
            uid: name
            for uid, name in db.execute(select(User.id, User.name).where(User.id.in_(creator_ids))).all()
        }
    for it in items:
        did = str(it.get("deptId") or "")
        if did and did not in dept_names:
            dept_names[did] = org_name(db, did)
        it["deptName"] = dept_names.get(did, "")
        it["createdByName"] = creators.get(str(it.get("createdById") or ""), "")
    return items


@router.get("/dept-stats", response_model=list[DeptTaskStat])
def dept_stats(db: Session = Depends(get_db), user: User = Depends(require_perm("task.view"))):
    """部门任务完成度 · 在 SQL 层聚合（GROUP BY），班组归集到其上级部门。"""
    today: date = reference_date()
    not_done = Task.done < Task.target
    q = select(
        Task.dept_id.label("dept_id"),
        func.count().label("total"),
        func.sum(case((Task.done >= Task.target, 1), else_=0)).label("done"),
        func.sum(case((and_(not_done, Task.end_date < today), 1), else_=0)).label("overdue"),
        func.sum(case((and_(not_done, Task.end_date == today), 1), else_=0)).label("due_soon"),
        func.sum(case((and_(Task.abnormal.is_(True), not_done), 1), else_=0)).label("risk"),
        func.avg(case((Task.target > 0, Task.done * 100.0 / Task.target), else_=0)).label("completion"),
    ).group_by(Task.dept_id)
    cond = scope_svc.visible_task_filter(db, user)
    if cond is not None:
        q = q.where(cond)

    orgs = {o.id: o for o in db.scalars(select(Organization)).all()}
    buckets: dict[str, dict] = {}
    for row in db.execute(q).all():
        org = orgs.get(row.dept_id)
        key = org.parent_id if (org and org.type == ORG_TYPE_TEAM and org.parent_id) else row.dept_id
        if key not in orgs:
            key = row.dept_id
        b = buckets.setdefault(
            key,
            {"deptId": key, "deptName": orgs[key].name if key in orgs else "未归属", "total": 0, "done": 0, "overdue": 0, "risk": 0, "dueSoon": 0, "_sum": 0.0, "_n": 0},
        )
        b["total"] += int(row.total or 0)
        b["done"] += int(row.done or 0)
        b["overdue"] += int(row.overdue or 0)
        b["risk"] += int(row.risk or 0)
        b["dueSoon"] += int(row.due_soon or 0)
        if row.completion is not None:
            b["_sum"] += float(row.completion) * int(row.total or 0)
            b["_n"] += int(row.total or 0)
    out = []
    for b in buckets.values():
        completion = round(b["_sum"] / b["_n"]) if b["_n"] else 0
        out.append(
            {
                "deptId": b["deptId"],
                "deptName": b["deptName"],
                "total": b["total"],
                "done": b["done"],
                "overdue": b["overdue"],
                "risk": b["risk"],
                "dueSoon": b["dueSoon"],
                "completion": completion,
            }
        )
    # 有风险的部门优先
    out.sort(key=lambda x: (-(x["overdue"] + x["risk"] + x["dueSoon"]), -x["total"], x["deptId"]))
    return out


@router.get("/import/template")
def task_template(db: Session = Depends(get_db), user: User = Depends(require_perm("task.import"))):
    return _xlsx(build_task_template(db), "重点任务导入标准模板.xlsx")


@router.post("/import", response_model=ImportResult)
async def task_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.import")),
):
    raw = await file.read()
    if len(raw) > settings.import_max_mb * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"文件不能超过 {settings.import_max_mb}MB")
    try:
        # 列名与模板共用同一常量，避免两处硬编码漂移
        rows = parse_rows(raw, TASK_COLUMNS, settings.import_max_rows, optional=TASK_OPTIONAL_COLUMNS)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    valid, errors = validate_task_rows(db, rows)
    if errors:
        return {"imported": 0, "errors": errors}
    count = import_tasks(db, valid, user)
    write_log(db, user, "import", "task", "", {"count": count}, request)
    db.commit()
    return {"imported": count, "errors": []}


@router.get("/export")
def task_export(db: Session = Depends(get_db), user: User = Depends(require_perm("task.view"))):
    rows = list(db.scalars(_visible_query(db, user).order_by(Task.id)).all())
    return _xlsx(export_tasks(db, rows), "重点任务清单.xlsx")


@router.get("", response_model=TaskListOut)
def list_tasks(
    keyword: str = "",
    dept_id: str = "",
    status: str = "",
    page: int = 1,
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.view")),
):
    page = max(1, page)
    q = _visible_query(db, user)
    if dept_id:
        q = q.where(Task.dept_id == dept_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(Task.parent.like(like), Task.title.like(like), Task.owner.like(like), Task.id.like(like)))
    cond = _status_condition(status, reference_date())
    if cond is not None:
        q = q.where(cond)

    # 分页与状态过滤都下推到 SQL：只读当前页，不再把全表读进内存后再切
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = list(db.scalars(q.order_by(Task.id).limit(size).offset((page - 1) * size)).all())
    return {"items": _enrich(db, [task_to_dict(t) for t in rows]), "total": total, "page": page, "size": size}


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(require_perm("task.view"))):
    task = _task_or_404(db, user, task_id)
    return _enrich(db, [task_to_dict(task)])[0]


def _apply_payload(db: Session, task: Task, payload, user: User) -> None:
    org = db.get(Organization, payload.dept_id)
    if not org:
        raise HTTPException(status_code=422, detail="责任部门不存在")
    try:
        start = datetime.strptime(payload.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(payload.end_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="日期格式应为 2026-10-01") from exc
    if end < start:
        raise HTTPException(status_code=422, detail="计划结束日期不能早于计划开始日期")
    task.parent = payload.parent.strip()
    task.title = (payload.title or "").strip() or None
    task.description = payload.description
    task.abnormal = bool(payload.abnormal)
    task.target = Decimal(str(payload.target))
    task.done = Decimal(str(payload.done))
    task.unit = payload.unit
    task.note = payload.note
    task.start_date = start
    task.end_date = end
    task.dept_id = payload.dept_id
    task.owner = payload.owner.strip()


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.edit")),
):
    tid = next_task_id(db)
    task = Task(id=tid, created_by=user.id)
    _apply_payload(db, task, payload, user)
    db.add(task)
    write_log(db, user, "create", "task", tid, {"parent": task.parent}, request)
    db.commit()
    db.refresh(task)
    return _enrich(db, [task_to_dict(task)])[0]


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.edit")),
):
    task = _task_or_404(db, user, task_id)
    if scope_svc.effective_scope(db, user) == "self" and task.owner != user.name:
        raise HTTPException(status_code=403, detail="仅可修改指派给本人的任务")
    _apply_payload(db, task, payload, user)
    write_log(db, user, "update", "task", task_id, {"parent": task.parent}, request)
    db.commit()
    db.refresh(task)
    return _enrich(db, [task_to_dict(task)])[0]


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.delete")),
):
    task = _task_or_404(db, user, task_id)
    db.delete(task)
    write_log(db, user, "delete", "task", task_id, {"parent": task.parent}, request)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": task_id}}
