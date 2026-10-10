"""达成率 / 红黄绿灯 / 回款 / 时间进度 / 任务健康度 纯函数测试。"""
from __future__ import annotations

from datetime import date

from app.models import MetricDef
from app.services.achievement import (
    calc_achievement,
    calc_progress,
    collection_light,
    deadline_of,
    is_task_done,
    light_of,
    task_health,
    time_progress_of,
    vs_time_progress,
)


def _def(**kw) -> MetricDef:
    base = dict(id="X", name="X", unit="", group="annual", family="", direction="positive", cycle="month", weight=1)
    base.update(kw)
    return MetricDef(**base)


def test_positive_achievement_and_light():
    d = _def(warn=0.95, danger=0.85)
    ach = calc_achievement(d, target=100, actual=80)
    assert ach and round(ach["rate"], 4) == 0.8
    assert light_of(d, 100, 80) == "red"
    assert light_of(d, 100, 96) == "amber"
    assert light_of(d, 100, 100) == "green"


def test_negative_metric():
    d = _def(direction="negative", warn=1.03, danger=1.1)
    assert light_of(d, 10, 8) == "green"
    assert light_of(d, 10, 10.5) == "amber"
    assert light_of(d, 10, 13) == "red"
    # 逆向指标零实际值视为达标
    ach = calc_achievement(d, target=10, actual=0)
    assert ach and ach["rate"] == float("inf")


def test_zero_target_metric():
    d = _def(direction="positive")
    assert light_of(d, 0, 0) == "green"
    assert light_of(d, 0, 2) == "red"
    ach = calc_achievement(d, target=0, actual=0)
    assert ach and ach["rate"] == 1


def test_missing_values():
    d = _def()
    assert calc_achievement(d, target=None, actual=10) is None
    assert light_of(d, None, 10) == "none"
    assert light_of(_def(no_target=True), 0, 1) == "none"


def test_collection_light():
    assert collection_light(0.96, 0.95) == "green"
    assert collection_light(0.92, 0.95) == "amber"
    assert collection_light(0.80, 0.95) == "red"
    assert collection_light(None, 0.95) == "none"


def test_time_progress_and_vs():
    tp = time_progress_of("2026-10")
    assert 0.7 < tp < 0.85
    assert vs_time_progress(tp, "2026-10") == 0


def test_task_progress_and_deadline():
    assert calc_progress(46000, 31800) == 69
    assert calc_progress(1, 0) == 0
    assert calc_progress(1, 1) == 100
    assert is_task_done(100, 100)

    today = date(2026, 10, 10)
    assert deadline_of(100, 50, date(2026, 10, 9), today)["level"] == "overdue"
    assert deadline_of(100, 50, date(2026, 10, 10), today)["level"] == "due_soon"
    assert deadline_of(100, 50, date(2026, 10, 11), today)["level"] == "normal"
    # 已完成任务即使过期也不判逾期
    assert deadline_of(100, 100, date(2026, 1, 1), today)["level"] == "done"
    # 异常叠加
    h = task_health(100, 50, date(2026, 11, 1), True, today)
    assert h["level"] == "risk" and h["label"] == "异常"
