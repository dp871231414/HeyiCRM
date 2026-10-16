"""市场项目路由：项目（商机）的增删改查。

**权限口径**：与任务模块一致 —— 列表 / 详情 / 编辑按**数据可见范围（scope）**隔离，
归属维度是「创建人所属部门」（项目本身没有部门字段）；
经营驾驶舱的漏斗统计不走这里，只按角色权限开放（见 `api/v1/dashboard.py`）。

注意与 `/projects`（项目公司，独立核算组织）区分：本模块是销售商机项目。
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.config import settings
from app.constants import MARKET_PROJECT_ID_PREFIX, MARKET_STAGE_VALUES, MARKET_STAGES
from app.core.deps import require_any_perm, require_perm
from app.db.session import get_db
from app.models import (
    MarketProject,
    Organization,
    ProjectProgress,
    ProjectTractorRequirement,
    ProjectTrailerRequirement,
    User,
)
from app.schemas.common import ImportResult
from app.schemas.project import (
    MarketProjectCreate,
    MarketProjectListOut,
    MarketProjectOut,
    MarketProjectUpdate,
    ProjectProgressCreate,
    ProjectProgressItem,
    ProjectProgressListOut,
)
from app.services import scope as scope_svc
from app.services.audit import write_log
from app.services.importer import (
    MARKET_PROJECT_COLUMNS,
    MARKET_PROJECT_OPTIONAL_COLUMNS,
    build_market_project_template,
    export_market_projects,
    import_market_projects,
    parse_rows,
    validate_market_project_rows,
)
from app.services.org_tree import market_tree_ids

router = APIRouter(prefix="/market-projects", tags=["项目管理"])

_STAGE_LABELS = {s["stage"]: s["label"] for s in MARKET_STAGES}

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

_SHEET_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=_SHEET_MIME,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def next_project_id(db: Session) -> str:
    """MP0001 递增（不复用已删除的号段）。"""
    max_seq = 0
    for pid in db.scalars(select(MarketProject.id)).all():
        m = re.fullmatch(rf"{MARKET_PROJECT_ID_PREFIX}(\d+)", pid)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"{MARKET_PROJECT_ID_PREFIX}{max_seq + 1:04d}"


def _to_dict(db: Session, p: MarketProject, creator_names: dict[str, str] | None = None) -> dict:
    if creator_names is None:
        creator_names = {}
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "latestProgress": p.progress or "",
        "tractorDemand": int(p.tractor_demand or 0),
        "trailerDemand": int(p.trailer_demand or 0),
        "stage": int(p.stage),
        "stageLabel": _STAGE_LABELS.get(int(p.stage), ""),
        "owner": p.owner,
        "ownerDeptId": p.owner_dept_id or "",
        "ownerDeptName": "",
        "createdById": p.created_by or "",
        "createdByName": creator_names.get(p.created_by or "", ""),
        "createdAt": p.created_at.isoformat() if p.created_at else "",
        "updatedAt": p.updated_at.isoformat() if p.updated_at else "",
    }


def _enrich_creators(db: Session, items: list[dict]) -> list[dict]:
    """批量补齐创建人姓名（去重一次查，避免 N+1）。"""
    ids = {it["createdById"] for it in items if it["createdById"]}
    names = {}
    if ids:
        names = {uid: name for uid, name in db.execute(select(User.id, User.name).where(User.id.in_(ids))).all()}
    for it in items:
        it["createdByName"] = names.get(it["createdById"], "")
    return items


def _enrich_owner_depts(db: Session, items: list[dict]) -> list[dict]:
    """批量补齐负责人所属部门名称（选负责人后自动带出的「所属部门」展示用）。"""
    ids = {it["ownerDeptId"] for it in items if it.get("ownerDeptId")}
    names = {}
    if ids:
        names = {oid: name for oid, name in db.execute(select(Organization.id, Organization.name).where(Organization.id.in_(ids))).all()}
    for it in items:
        it["ownerDeptName"] = names.get(it.get("ownerDeptId"), "")
    return items


def _enrich_progress(db: Session, items: list[dict]) -> list[dict]:
    """批量补齐「最新进展」快照（market_project.progress，冗余自最近一条 ProjectProgress）。"""
    ids = {it["id"] for it in items}
    latest: dict[str, str] = {}
    if ids:
        rows = db.execute(
            select(ProjectProgress.project_id, ProjectProgress.id, ProjectProgress.content)
            .where(ProjectProgress.project_id.in_(ids))
            .order_by(ProjectProgress.id.asc())
        ).all()
        for pid, _rid, content in rows:
            latest[pid] = content  # 升序遍历，后写覆盖 → 每项目留下最新一条
    for it in items:
        it["latestProgress"] = latest.get(it["id"], "")
    return items


def _req_item(r) -> dict:
    return {"id": r.id, "model": r.model or "", "battery": r.battery or "", "qty": int(r.qty or 0)}


def _enrich_requirements(db: Session, items: list[dict]) -> list[dict]:
    """批量补齐车头 / 挂车需求明细子列表（供编辑/详情表单预填，列表也一并带出）。

    列表「车头数量 / 挂车数量」仍是 market_project 上的汇总快照，这里额外带出明细。
    """
    ids = {it["id"] for it in items}
    if not ids:
        return items
    t_rows = db.scalars(
        select(ProjectTractorRequirement)
        .where(ProjectTractorRequirement.project_id.in_(ids))
        .order_by(ProjectTractorRequirement.id)
    ).all()
    tr_rows = db.scalars(
        select(ProjectTrailerRequirement)
        .where(ProjectTrailerRequirement.project_id.in_(ids))
        .order_by(ProjectTrailerRequirement.id)
    ).all()
    t_map: dict[str, list[dict]] = {}
    tr_map: dict[str, list[dict]] = {}
    for r in t_rows:
        t_map.setdefault(r.project_id, []).append(_req_item(r))
    for r in tr_rows:
        tr_map.setdefault(r.project_id, []).append(_req_item(r))
    for it in items:
        it["tractorRequirements"] = t_map.get(it["id"], [])
        it["trailerRequirements"] = tr_map.get(it["id"], [])
    return items


def _reconcile_requirements(db: Session, project_id: str, items: list, model_cls) -> None:
    """项目需求明细子列表整份替换：先删后插（编辑界面可增删多行）。"""
    db.query(model_cls).filter(model_cls.project_id == project_id).delete()
    for x in items or []:
        db.add(
            model_cls(
                project_id=project_id,
                model=(x.model or "").strip(),
                battery=(x.battery or "").strip(),
                qty=int(x.qty or 0),
            )
        )


def _visible_query(db: Session, user: User):
    q = select(MarketProject)
    cond = scope_svc.visible_market_project_filter(db, user)
    if cond is not None:
        q = q.where(cond)
    return q


def _project_or_404(db: Session, user: User, project_id: str) -> MarketProject:
    p = db.get(MarketProject, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    cond = scope_svc.visible_market_project_filter(db, user)
    if cond is not None:
        visible = db.scalar(select(MarketProject).where(MarketProject.id == project_id, cond))
        if not visible:
            raise HTTPException(status_code=403, detail="无权访问该项目")
    return p


def _apply_payload(p: MarketProject, payload) -> None:
    if payload.stage not in MARKET_STAGE_VALUES:
        raise HTTPException(status_code=422, detail="项目阶段不合法")
    p.name = payload.name.strip()
    if not p.name:
        raise HTTPException(status_code=422, detail="项目名称不能为空")
    p.description = payload.description or ""
    p.stage = int(payload.stage)
    p.owner = payload.owner.strip()
    p.owner_dept_id = payload.owner_dept_id or None
    # 车头 / 挂车需求数 = 明细子列表「数量」汇总（列表 / 驾驶舱展示汇总值，保持与 funnel.py 口径一致）
    p.tractor_demand = sum(int(x.qty or 0) for x in (payload.tractorRequirements or []))
    p.trailer_demand = sum(int(x.qty or 0) for x in (payload.trailerRequirements or []))


@router.get("", response_model=MarketProjectListOut)
def list_projects(
    keyword: str = "",
    stage: int | None = None,
    page: int = 1,
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.view")),
):
    page = max(1, page)
    q = _visible_query(db, user)
    if stage is not None:
        q = q.where(MarketProject.stage == stage)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(or_(MarketProject.name.like(like), MarketProject.owner.like(like), MarketProject.id.like(like)))

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = list(db.scalars(q.order_by(MarketProject.id).limit(size).offset((page - 1) * size)).all())
    return {
        "items": _enrich_requirements(
            db,
            _enrich_progress(
                db, _enrich_owner_depts(db, _enrich_creators(db, [_to_dict(db, p) for p in rows]))
            ),
        ),
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/export")
def market_project_export(db: Session = Depends(get_db), user: User = Depends(require_perm("market.view"))):
    rows = list(db.scalars(_visible_query(db, user).order_by(MarketProject.id)).all())
    return _xlsx(export_market_projects(db, rows), "市场项目清单.xlsx")


@router.get("/{project_id}", response_model=MarketProjectOut)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_perm(["market.view", "market.detail"])),
):
    p = _project_or_404(db, user, project_id)
    return _enrich_requirements(
        db, _enrich_progress(db, _enrich_owner_depts(db, _enrich_creators(db, [_to_dict(db, p)])))
    )[0]


@router.post("", response_model=MarketProjectOut, status_code=201)
def create_project(
    payload: MarketProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.edit")),
):
    pid = next_project_id(db)
    p = MarketProject(id=pid, created_by=user.id)
    _apply_payload(p, payload)
    # 项目进展必填：写入项目快照（列表/导出用）并作为第一条进展记录
    p.progress = payload.progress
    db.add(p)
    db.flush()  # 先拿到 project_id 再写进展记录与需求明细
    db.add(ProjectProgress(project_id=pid, content=payload.progress, created_by=user.id))
    _reconcile_requirements(db, pid, payload.tractorRequirements, ProjectTractorRequirement)
    _reconcile_requirements(db, pid, payload.trailerRequirements, ProjectTrailerRequirement)
    write_log(db, user, "create", "market_project", pid, {"name": p.name}, request)
    db.commit()
    db.refresh(p)
    return _enrich_requirements(
        db, _enrich_progress(db, _enrich_owner_depts(db, _enrich_creators(db, [_to_dict(db, p)])))
    )[0]


@router.patch("/{project_id}", response_model=MarketProjectOut)
def update_project(
    project_id: str,
    payload: MarketProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.edit")),
):
    p = _project_or_404(db, user, project_id)
    _apply_payload(p, payload)
    # 编辑不直接改进展快照（只能通过「新增进展」追加记录），此处保持 p.progress 不变
    _reconcile_requirements(db, p.id, payload.tractorRequirements, ProjectTractorRequirement)
    _reconcile_requirements(db, p.id, payload.trailerRequirements, ProjectTrailerRequirement)
    write_log(db, user, "update", "market_project", project_id, {"name": p.name}, request)
    db.commit()
    db.refresh(p)
    return _enrich_requirements(
        db, _enrich_progress(db, _enrich_owner_depts(db, _enrich_creators(db, [_to_dict(db, p)])))
    )[0]


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.delete")),
):
    p = _project_or_404(db, user, project_id)
    # 级联删除进展记录与需求明细，避免孤儿记录被后续新建项目（复用项目 ID）误继承
    db.query(ProjectProgress).filter(ProjectProgress.project_id == p.id).delete()
    db.query(ProjectTractorRequirement).filter(ProjectTractorRequirement.project_id == p.id).delete()
    db.query(ProjectTrailerRequirement).filter(ProjectTrailerRequirement.project_id == p.id).delete()
    db.delete(p)
    write_log(db, user, "delete", "market_project", project_id, {"name": p.name}, request)
    db.commit()
    return {"ok": True, "msg": "已删除", "data": {"id": project_id}}


# ------------------------------------------------------------------ 进展记录（时间轴）
#
# 规则：编辑界面不可直接改进展，只能「新增进展」追加记录；历史按时间倒序分页，
# 前端默认展示最近 5 条、下拉加载更早记录。market_project.progress 始终冗余最新一条，供列表列/导出。


@router.get("/{project_id}/progress", response_model=ProjectProgressListOut)
def list_project_progress(
    project_id: str,
    page: int = 1,
    size: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_perm(["market.view", "market.detail"])),
):
    p = _project_or_404(db, user, project_id)
    page = max(1, page)
    q = select(ProjectProgress).where(ProjectProgress.project_id == p.id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = list(
        db.scalars(q.order_by(ProjectProgress.id.desc()).limit(size).offset((page - 1) * size)).all()
    )
    creator_ids = {r.created_by for r in rows if r.created_by}
    creators: dict[str, str] = (
        {uid: name for uid, name in db.execute(select(User.id, User.name).where(User.id.in_(creator_ids))).all()}
        if creator_ids
        else {}
    )
    return {
        "items": [
            ProjectProgressItem(
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


@router.post("/{project_id}/progress", response_model=ProjectProgressItem, status_code=201)
def add_project_progress(
    project_id: str,
    payload: ProjectProgressCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.edit")),
):
    p = _project_or_404(db, user, project_id)
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="进展内容不能为空")
    record = ProjectProgress(project_id=p.id, content=content, created_by=user.id)
    db.add(record)
    p.progress = content  # 冗余快照同步为最新一条
    db.flush()
    write_log(db, user, "progress", "market_project", p.id, {"progress_id": record.id}, request)
    db.commit()
    db.refresh(record)
    return ProjectProgressItem(
        id=record.id,
        content=record.content,
        createdById=user.id,
        createdByName=user.name,
        createdAt=record.created_at.isoformat() if record.created_at else "",
    )


@router.get("/import/template")
def market_project_template(db: Session = Depends(get_db), user: User = Depends(require_perm("market.import"))):
    return _xlsx(build_market_project_template(db), "市场项目导入标准模板.xlsx")


@router.post("/import", response_model=ImportResult)
async def market_project_import(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.import")),
):
    raw = await file.read()
    if len(raw) > settings.import_max_mb * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"文件不能超过 {settings.import_max_mb}MB")
    try:
        rows = parse_rows(raw, MARKET_PROJECT_COLUMNS, settings.import_max_rows, optional=MARKET_PROJECT_OPTIONAL_COLUMNS)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    valid, errors = validate_market_project_rows(db, rows)
    if errors:
        return {"imported": 0, "errors": errors}
    count = import_market_projects(db, valid, user)
    write_log(db, user, "import", "market_project", "", {"count": count}, request)
    db.commit()
    return {"imported": count, "errors": []}


@router.post("/reseed", status_code=200)
def reseed_projects(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("market.edit")),
):
    """按市场部人员清单重新生成项目数据。

    删除全部现有市场项目，再为「市场部及其下属部门」内的每个**启用**人员生成 1 个市场项目
    （负责人 = 该人员，所属部门 = 其直接部门，阶段 / 牵引车 / 挂车需求按确定规则生成，
    便于线上线下用同一套逻辑得到一致、无脏引用的数据）。

    生成规则（确定性，与人员顺序无关地可复现）：
    - 阶段按 MARKET_STAGE_VALUES 循环取（10→25→…→100→10…）
    - 牵引车需求 = 20 + (序号 × 53) % 200（20~219 辆）
    - 挂车需求 = 牵引车 × 3 // 5（约 0.6 倍）
    项目 ID 沿用 MP 递增号段（清空后从 MP0001 起）。
    """
    from app.constants import MARKET_STAGE_VALUES

    # 1) 清空现有项目（含其审计引用由数据库外键置空处理）
    #    会话 autoflush=False，DELETE 已立即执行；此处再 flush 一次，确保后续 next_project_id
    #    读到的「最大已用 ID」是清空后的状态，而不残留旧号段。
    db.execute(delete(ProjectTractorRequirement))
    db.execute(delete(ProjectTrailerRequirement))
    db.execute(delete(MarketProject))
    db.flush()

    # 2) 取市场部子树内的启用人员，按部门 + 账号稳定排序
    market_ids = market_tree_ids(db)
    users = (
        db.execute(
            select(User)
            .where(User.status == "active", User.dept_id.in_(market_ids))
            .order_by(User.dept_id, User.id)
        )
        .scalars()
        .all()
    )

    created = 0
    for idx, u in enumerate(users):
        stage = MARKET_STAGE_VALUES[idx % len(MARKET_STAGE_VALUES)]
        tractor = 20 + (idx * 53) % 200
        trailer = tractor * 3 // 5
        pid = next_project_id(db)
        p = MarketProject(
            id=pid,
            name=f"{u.name}负责的市场项目",
            description=f"系统按市场部人员清单自动生成（负责人 {u.name}）",
            tractor_demand=tractor,
            trailer_demand=trailer,
            stage=stage,
            owner=u.name,
            owner_dept_id=u.dept_id,
            created_by=user.id,
        )
        db.add(p)
        # 立即 flush：让下一轮 next_project_id 读到本行已写入的 ID（会话 autoflush=False，
        # 不清空也会因读不到刚插入的行而重复生成 MP0001，导致主键冲突）。
        db.flush()
        # 需求明细：按汇总值各补一行（型号留空，数量=汇总值），保证列表汇总与明细一致，
        # 编辑表单预填时也带得出数据。
        db.add(ProjectTractorRequirement(project_id=pid, model="", battery="", qty=tractor))
        db.add(ProjectTrailerRequirement(project_id=pid, model="", battery="", qty=trailer))
        created += 1

    db.commit()
    write_log(
        db,
        user,
        "reseed",
        "market_project",
        "global",
        {"deleted": "all", "created": created, "marketUsers": len(users)},
        request,
    )
    return {"ok": True, "msg": f"已按 {len(users)} 名市场部人员重新生成 {created} 个项目", "created": created}
