"""市场项目漏斗：阶段统计与销量预测。

口径说明：
- **漏斗按「各阶段当前数量」统计** —— 每一层只统计当前阶段
  （stage == 该层）的项目数 / 需求车辆数 / 需求挂车数，不向上累计。
  这样每层标题下显示的就是「停在这个阶段」的实有数量，而非到本层为止的累计。
- **销量预测按项目各自阶段的转化概率加权** ——
  预测销量 = Σ（项目需求数 × 该项目所在阶段的转化概率）。
  转化概率默认与阶段百分比一致（10%→0.10 … 100%→1.00），
  可在驾驶舱「市场项目概览」模块配置（存 funnel_config 表，全系统共用一份）。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import MARKET_STAGES
from app.models import FunnelConfig, MarketProject


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


def build_funnel(db: Session) -> dict:
    """漏斗统计 + 加权销量预测。驾驶舱只按角色权限开放，不做数据范围裁剪。"""
    rows = db.execute(
        select(
            MarketProject.stage,
            func.count(),
            func.coalesce(func.sum(MarketProject.tractor_demand), 0),
            func.coalesce(func.sum(MarketProject.trailer_demand), 0),
        ).group_by(MarketProject.stage)
    ).all()
    per_stage = {stage: (int(cnt), int(trac), int(trai)) for stage, cnt, trac, trai in rows}
    probs = load_probs(db)

    stages = []
    for meta in MARKET_STAGES:
        v = meta["stage"]
        # 各阶段当前数量：仅统计 stage == 该层的项目（不向上累计）
        cnt, trac, trai = per_stage.get(v, (0, 0, 0))
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
    }
