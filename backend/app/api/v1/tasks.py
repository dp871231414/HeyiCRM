"""任务路由：增删改查、部门完成度聚合、导入导出。

**权限口径**：任务模块是本系统**唯一**按数据可见范围（scope）隔离数据的模块 ——
列表、详情、统计均只返回登录人可见范围（全公司 / 本部门及下属 / 本部门 / 本人）内的数据。
经营驾驶舱与指标维护只按角色权限判断能否查看，见各自的模块说明。
"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import ColumnElement, and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ORG_TYPE_TEAM
from app.core.deps import get_user_perms, require_any_perm, require_perm
from app.db.session import get_db
from app.models import MainTask, Organization, Task, TaskProgress, User
from app.schemas.common import ImportResult
from app.schemas.task import (
    DeptTaskStat,
    TaskCreate,
    TaskListOut,
    TaskOut,
    TaskProgressCreate,
    TaskProgressItem,
    TaskProgressListOut,
    TaskUpdate,
)
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
    """批量补齐展示用名称：责任部门名 + 创建人名 + 主任务名 + 责任人 ID。

    创建人由 created_by（用户 ID）解析为姓名，责任人与其 user.id 也一并补齐
    （分组视图需按人员 ID 排序）；组织名、用户名、主任务名都做去重缓存，避免 N+1。
    """
    dept_names: dict[str, str] = {}
    creator_ids = {str(it.get("createdById") or "") for it in items} - {""}
    creators: dict[str, str] = {}
    if creator_ids:
        creators = {
            uid: name
            for uid, name in db.execute(select(User.id, User.name).where(User.id.in_(creator_ids))).all()
        }
    # 责任人姓名 → user.id（用于分组视图「按人员 ID 排序」）
    owner_ids: dict[str, str] = {
        name: uid for uid, name in db.execute(select(User.id, User.name)).all()
    }
    # 主任务名映射
    mt_ids = {str(it.get("mainTaskId") or "") for it in items} - {""}
    mt_names: dict[str, str] = {}
    if mt_ids:
        mt_names = {
            mid: name
            for mid, name in db.execute(select(MainTask.id, MainTask.name).where(MainTask.id.in_(mt_ids))).all()
        }
    # 最新进展记录（列表「进展描述」列）：按 id 取每个任务最大一条（自增主键即时间序）
    task_ids = {str(it.get("id") or "") for it in items} - {""}
    latest_progress: dict[str, str] = {}
    if task_ids:
        rows = db.execute(
            select(TaskProgress.task_id, TaskProgress.id, TaskProgress.content)
            .where(TaskProgress.task_id.in_(task_ids))
            .order_by(TaskProgress.id.asc())
        ).all()
        for tid, _pid, content in rows:
            latest_progress[tid] = content  # 升序遍历，后写覆盖 → 每任务留下最新一条
    for it in items:
        did = str(it.get("deptId") or "")
        if did and did not in dept_names:
            dept_names[did] = org_name(db, did)
        it["deptName"] = dept_names.get(did, "")
        it["createdByName"] = creators.get(str(it.get("createdById") or ""), "")
        it["ownerId"] = owner_ids.get((it.get("owner") or "").strip(), "") or owner_ids.get(it.get("owner") or "", "")
        mt_id = str(it.get("mainTaskId") or "")
        it["mainTaskName"] = mt_names.get(mt_id, "")
        it["latestProgress"] = latest_progress.get(str(it.get("id") or ""), "")
        # 兼容旧字段：title 沿用主任务名（无主任务时为空）
        if it.get("title") is None:
            it["title"] = it["mainTaskName"]
    return items


def created_range_of(period: str, scope: str) -> tuple[datetime, datetime] | None:
    """按「页面顶部统计周期」推导创建时间的 [起, 止) 区间（止为开区间）。

    scope：`month` 当月 / `year` 本年 —— 年份同样取周期所在年，
    保证「当月新增」与「本年新增」和页面当前月份同源，不跟随服务器当天。
    """
    try:
        year, month = (int(x) for x in str(period).split("-")[:2])
    except (ValueError, TypeError):
        return None
    try:
        if scope == "year":
            start, end = date(year, 1, 1), date(year + 1, 1, 1)
        else:
            start = date(year, month, 1)
            end = date(year + 1 if month == 12 else year, 1 if month == 12 else month + 1, 1)
    except ValueError:  # 月份越界等非法周期：不筛，退回全部
        return None
    return datetime.combine(start, time.min), datetime.combine(end, time.min)


def dept_task_filter(period: str, filter: str) -> ColumnElement[bool] | None:
    """「部门任务完成度」的筛选条件。

    all   全部 —— 不加条件（默认）；
    year  本年新增 / month 当月新增 —— 取所选时间范围内创建的任务；
    open  未结束 —— 未完成（done < target），含进行中与逾期。

    创建时间由数据库默认写入（UTC），跨月边界时与北京时间可能差 8 小时，
    属已知且可接受的口径误差（任务量级下不影响判断）。
    """
    if filter in ("year", "month"):
        bounds = created_range_of(period, filter)
        if bounds is None:
            return None
        start, end = bounds
        return and_(Task.created_at >= start, Task.created_at < end)
    if filter == "open":
        return Task.done < Task.target
    return None


def dept_stats_all(
    db: Session,
    cond: ColumnElement[bool] | None = None,
    task_filter: ColumnElement[bool] | None = None,
) -> list[dict]:
    """部门任务完成度 · 在 SQL 层聚合（GROUP BY），班组归集到其上级部门。

    `cond` 为可见性条件：
    - 任务模块传入 `visible_task_filter(...)` —— 按数据范围隔离；
    - 经营驾驶舱不传 —— 该模块只按角色权限开放，任务统计同样按全量口径参与经营分析。

    `task_filter` 为展示口径筛选（全部 / 本年新增 / 当月新增 / 未结束），
    由 `dept_task_filter(...)` 生成，与 `cond` 是「与」关系。
    """
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
    if cond is not None:
        q = q.where(cond)
    if task_filter is not None:
        q = q.where(task_filter)

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


@router.get("/dept-stats", response_model=list[DeptTaskStat])
def dept_stats(db: Session = Depends(get_db), user: User = Depends(require_perm("task.view"))):
    """任务模块的部门完成度 · 按数据可见范围隔离。"""
    return dept_stats_all(db, scope_svc.visible_task_filter(db, user))


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
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_perm(["task.view", "task.detail"])),
):
    task = _task_or_404(db, user, task_id)
    return _enrich(db, [task_to_dict(task)])[0]


# 系统默认主任务：任务未选择主任务时默认关联它
MT_NONE_ID = "MT_NONE"


def _apply_payload(db: Session, task: Task, payload, user: User) -> None:
    """写入任务的业务字段。注意：不写 task.note —— 进展描述只能通过「新增进展」追加记录。"""
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
    # 主任务：不选择 → 默认关联系统「空」；选择 → 校验存在
    mt_id = payload.main_task_id or MT_NONE_ID
    mt = db.get(MainTask, mt_id)
    if not mt:
        raise HTTPException(status_code=422, detail="主任务不存在")
    task.parent = payload.parent.strip()
    task.title = mt.name  # 冗余存储，便于旧查询 / 导出兼容
    task.main_task_id = mt_id
    task.description = payload.description
    task.abnormal = bool(payload.abnormal)
    task.target = Decimal(str(payload.target))
    task.done = Decimal(str(payload.done))
    task.unit = payload.unit
    task.start_date = start
    task.end_date = end
    task.dept_id = payload.dept_id
    task.owner = payload.owner.strip()
    # 主任务（非「空」）首次被任务选用时，将其 责任人/责任部门 回填为当前任务的责任人/部门。
    # 设计约定：主任务创建时这两项为空，主任务名下第一个任务保存时由该任务带出；
    # 已有值则保留（不覆盖人工维护结果）。改名只改 name，ID 不变，故回填只认非「空」主任务。
    if mt_id != MT_NONE_ID and mt is not None:
        if not mt.owner_id:
            u = db.scalar(select(User).where(User.name == task.owner))
            mt.owner_id = u.id if u else None
        if not mt.dept_id:
            mt.dept_id = task.dept_id


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
    # 进展描述必填：写入任务快照（列表/导出用）并作为第一条进展记录
    task.note = payload.note
    db.add(task)
    db.flush()  # 先拿到 task.id 再写进展记录
    db.add(TaskProgress(task_id=tid, content=payload.note, created_by=user.id))
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
    # 级联删除进展记录，避免孤儿记录被后续新建任务（复用任务 ID）误继承
    db.query(TaskProgress).filter(TaskProgress.task_id == task.id).delete()
    db.delete(task)
    write_log(db, user, "delete", "task", task_id, {"parent": task.parent}, request)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": task_id}}


# ------------------------------------------------------------------ 进展记录（时间轴）
#
# 规则：编辑界面不可直接改进展描述，只能「新增进展」追加记录；历史按时间倒序分页，
# 前端默认展示最近 5 条、下拉加载更早记录。task.note 始终冗余最新一条，供列表列/导出。


@router.get("/{task_id}/progress", response_model=TaskProgressListOut)
def list_task_progress(
    task_id: str,
    page: int = 1,
    size: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_perm(["task.view", "task.detail"])),
):
    task = _task_or_404(db, user, task_id)
    page = max(1, page)
    q = select(TaskProgress).where(TaskProgress.task_id == task.id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = list(
        db.scalars(q.order_by(TaskProgress.id.desc()).limit(size).offset((page - 1) * size)).all()
    )
    creator_ids = {r.created_by for r in rows if r.created_by}
    creators: dict[str, str] = (
        {uid: name for uid, name in db.execute(select(User.id, User.name).where(User.id.in_(creator_ids))).all()}
        if creator_ids
        else {}
    )
    return {
        "items": [
            TaskProgressItem(
                id=r.id,
                content=r.content,
                createdById=r.created_by or "",
                createdByName=creators.get(r.created_by or "", ""),
                createdAt=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/{task_id}/progress", response_model=TaskProgressItem, status_code=201)
def add_task_progress(
    task_id: str,
    payload: TaskProgressCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("task.edit")),
):
    task = _task_or_404(db, user, task_id)
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="进展内容不能为空")
    record = TaskProgress(task_id=task.id, content=content, created_by=user.id)
    db.add(record)
    task.note = content  # 冗余快照同步为最新一条
    db.flush()
    write_log(db, user, "progress", "task", task.id, {"progress_id": record.id}, request)
    db.commit()
    db.refresh(record)
    return TaskProgressItem(
        id=record.id,
        content=record.content,
        createdById=user.id,
        createdByName=user.name,
        createdAt=record.created_at.isoformat() if record.created_at else "",
    )
