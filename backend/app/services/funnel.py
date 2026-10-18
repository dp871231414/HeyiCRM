"""市场项目漏斗：阶段统计与销量预测。

口径说明：
- **漏斗按「各阶段当前数量」统计** —— 每一层只统计当前阶段
  （stage == 该层）的项目数 / 需求车辆数 / 需求挂车数，不向上累计。
  这样每层标题下显示的就是「停在这个阶段」的实有数量，而非到本层为止的累计。
- **销量预测按项目各自阶段的转化概率加权** ——
  预测销量 = Σ（项目需求数 × 该项目所在阶段的转化概率）。
  转化概率默认与阶段百分比一致（10→0.10 … 100→1.00），
  可在驾驶舱「市场项目概览」模块配置（存 funnel_config 表，全系统共用一份）。

筛选（dept_id）：
- 经营驾驶舱「市场项目概览」按市场部二级部门提供筛选标签。
- 传入具体二级部门 ID 时，只统计负责人直接归属该部门的项目；
- 不传（None / 全部）时，统计负责人属于「市场部及其下属部门」全部人员的项目。
- 负责人是自由文本姓名，这里按用户表映射其所属部门，避免脏数据（owner 指向已不存在的人）污染统计。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DEMAND_ANALYSIS_STAGES, MARKET_STAGES
from app.models import FunnelConfig, MarketProject, ProjectTractorRequirement, ProjectTrailerRequirement, User
from app.services.org_tree import market_sub_departments, market_tree_ids


def _round_half_up(x: float) -> int:
    """预估消化数量按「四舍五入」取整（车辆数不保留小数）。

    用 int(x + 0.5) 实现「逢 .5 向上」的常规四舍五入（digest 恒非负，无需处理负数场景）。
    不用内置 round()：其 banker's rounding（2.5→2）不符合「保留整数」的直觉预期。
    """
    return int(x + 0.5)


def load_probs(db: Session) -> dict[int, float]:
    """各阶段转化概率；库里没配过的阶段按阶段百分比回落（10→0.10）。"""
    configured = {row.stage: float(row.prob) for row in db.scalars(select(FunnelConfig)).all()}
    return {s["stage"]: configured.get(s["stage"], s["stage"] / 100.0) for s in MARKET_STAGES}


def save_probs(db: Session, probs: dict[int, float]) -> dict[int, float]:
    """覆盖写入全部六个阶段的概率（整份保存，避免半更新状态）。"""
    for stage in (s["stage"] for s in MARKET_STAGES):
        row = db.get(FunnelConfig, stage)
        if row is None:
            db.add(FunnelConfig(stage=stage, prob=float(probs[stage])))
        else:
            row.prob = float(probs[stage])
    db.flush()
    return load_probs(db)


def _owner_dept_map(db: Session, market_ids: set[str]) -> dict[str, str]:
    """活跃用户「姓名 → 所属部门」映射，仅纳入市场部子树内的人员（作为有效负责人）。"""
    rows = db.execute(select(User.name, User.dept_id).where(User.status == "active")).all()
    return {name: dept for name, dept in rows if dept in market_ids}


def build_funnel(db: Session, dept_id: str | None = None) -> dict:
    """漏斗统计 + 加权销量预测。驾驶舱只按角色权限开放，不做数据范围裁剪。

    dept_id：指定二级部门 ID 时只统计该部门负责人的项目；为 None 时统计市场部子树全部负责人。
    """
    market_ids = market_tree_ids(db)
    owner_dept = _owner_dept_map(db, market_ids)

    if dept_id:
        # 具体二级部门：负责人直接归属该部门
        keep = {name for name, did in owner_dept.items() if did == dept_id}
    else:
        # 全部：市场部及其下属部门全体人员
        keep = {name for name, did in owner_dept.items() if did in market_ids}

    rows = db.scalars(select(MarketProject)).all()
    per_stage: dict[int, list[int]] = {}
    for p in rows:
        if p.owner not in keep:
            continue
        v = per_stage.setdefault(int(p.stage), [0, 0, 0])
        v[0] += 1
        v[1] += int(p.tractor_demand or 0)
        v[2] += int(p.trailer_demand or 0)

    probs = load_probs(db)
    stages = []
    for meta in MARKET_STAGES:
        v = meta["stage"]
        cnt, trac, trai = per_stage.get(v, [0, 0, 0])
        stages.append(
            {
                "stage": v,
                "label": meta["label"],
                "prob": probs[v],
                "count": cnt,
                "tractor": trac,
                "trailer": trai,
            }
        )

    forecast_tractor = sum(t * probs[s] for s, (_, t, _) in per_stage.items() if s in probs)
    forecast_trailer = sum(t * probs[s] for s, (_, _, t) in per_stage.items() if s in probs)
    return {
        "stages": stages,
        "forecast": {
            # 加权结果保留整数辆（四舍五入），小数辆没有业务含义
            "tractor": round(forecast_tractor),
            "trailer": round(forecast_trailer),
        },
        # 市场部直接子部门（二级部门）列表，供前端渲染筛选标签；随组织变化同步更新
        "deptOptions": market_sub_departments(db),
    }


def build_demand_analysis(db: Session, dept_id: str | None = None) -> dict:
    """车辆需求分析：车头按(车型+电池容量)组合、挂车按车型分行统计实际录入的需求明细。

    - 车头需求：每种(车型, 电池容量)组合的汇总需求数量（辆）。
    - 挂车需求：每种车型的「总数量」（辆）与「预估消化数量」（辆）= Σ(需求数量 × 项目所在阶段转化概率)。
    - 同时按阶段切分（byStage，key 为字符串 stage）与全量（all）两套，供前端按阶段筛选标签切换。

    只按角色权限开放，不做数据范围裁剪（与驾驶舱其余模块同一口径）。
    dept_id：指定二级部门时只统计该部门负责人名下的项目；为 None 时统计市场部子树全部负责人。
    """
    market_ids = market_tree_ids(db)
    owner_dept = _owner_dept_map(db, market_ids)

    if dept_id:
        keep = {name for name, did in owner_dept.items() if did == dept_id}
    else:
        keep = {name for name, did in owner_dept.items() if did in market_ids}

    projects = db.scalars(select(MarketProject)).all()
    # 仅纳入「负责人属于统计范围」的项目，记录其阶段
    proj_stage: dict[str, int] = {}
    for p in projects:
        if p.owner not in keep:
            continue
        proj_stage[p.id] = int(p.stage)

    probs = load_probs(db)

    tractor_reqs = db.scalars(select(ProjectTractorRequirement)).all()
    trailer_reqs = db.scalars(select(ProjectTrailerRequirement)).all()

    # 车头：按 (车型, 电池容量) 组合，分别按阶段与全量聚合；
    # qty=该组合下所有命中项目对应组合的车头需求之和，digest=Σ(需求数 × 项目所在阶段转化概率)
    tractor_by_stage: dict[int, dict[tuple[str, str], dict[str, float]]] = {}
    tractor_all: dict[tuple[str, str], dict[str, float]] = {}
    for r in tractor_reqs:
        s = proj_stage.get(r.project_id)
        if s is None:
            continue
        key = (r.model or "未填", r.battery or "未填")
        q = int(r.qty)
        d = q * probs.get(s, s / 100.0)
        agg = tractor_all.get(key, {"qty": 0.0, "digest": 0.0})
        agg["qty"] += q
        agg["digest"] += d
        tractor_all[key] = agg
        ts = tractor_by_stage.setdefault(s, {})
        ta = ts.get(key, {"qty": 0.0, "digest": 0.0})
        ta["qty"] += q
        ta["digest"] += d
        ts[key] = ta

    # 挂车：按车型，分别按阶段与全量聚合；digest = qty × 项目所在阶段转化概率
    trailer_by_stage: dict[int, dict[str, dict[str, float]]] = {}
    trailer_all: dict[str, dict[str, float]] = {}
    for r in trailer_reqs:
        s = proj_stage.get(r.project_id)
        if s is None:
            continue
        key = r.model or "未填"
        q = int(r.qty)
        d = q * probs.get(s, s / 100.0)
        agg = trailer_all.get(key, {"qty": 0.0, "digest": 0.0})
        agg["qty"] += q
        agg["digest"] += d
        trailer_all[key] = agg
        ts = trailer_by_stage.setdefault(s, {})
        ta = ts.get(key, {"qty": 0.0, "digest": 0.0})
        ta["qty"] += q
        ta["digest"] += d
        ts[key] = ta

    # 阶段元信息：含流失阶段（置于最后），供前端渲染筛选标签；流失转化率固定 0%
    stages_meta = [
        {"stage": m["stage"], "label": m["label"], "prob": probs.get(m["stage"], m["stage"] / 100.0)}
        for m in DEMAND_ANALYSIS_STAGES
    ]

    def sort_tractor(d: dict[tuple[str, str], dict[str, float]]):
        # 数量降序，数量相同按车型、电池容量字典序，结果稳定
        return sorted(d.items(), key=lambda kv: (-kv[1]["qty"], kv[0][0], kv[0][1]))

    def sort_trailer(d: dict[str, dict[str, float]]):
        return sorted(d.items(), key=lambda kv: (-kv[1]["qty"], kv[0]))

    tractor = {
        "all": [{"model": k[0], "battery": k[1], "qty": int(v["qty"]), "digest": _round_half_up(v["digest"])} for k, v in sort_tractor(tractor_all)],
        "byStage": {
            str(s): [{"model": k[0], "battery": k[1], "qty": int(v["qty"]), "digest": _round_half_up(v["digest"])} for k, v in sort_tractor(d)]
            for s, d in tractor_by_stage.items()
        },
    }
    trailer = {
        "all": [
            {"model": k, "qty": int(v["qty"]), "digest": _round_half_up(v["digest"])}
            for k, v in sort_trailer(trailer_all)
        ],
        "byStage": {
            str(s): [
                {"model": k, "qty": int(v["qty"]), "digest": _round_half_up(v["digest"])}
                for k, v in sort_trailer(d)
            ]
            for s, d in trailer_by_stage.items()
        },
    }
    return {"stages": stages_meta, "tractor": tractor, "trailer": trailer}
