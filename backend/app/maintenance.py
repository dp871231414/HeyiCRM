"""数据维护工具（一次性运维动作，不暴露为 HTTP 接口）。

用法：
    .venv/bin/python -m app.maintenance purge --keep chenzm,huguohai --dry-run
    .venv/bin/python -m app.maintenance purge --keep chenzm,huguohai
    .venv/bin/python -m app.maintenance purge --keep chenzm --no-tasks

为什么不做成接口：删除账号、清空任务都是**不可逆**动作，不需要在日常界面上暴露。
需要时由运维显式执行一次即可（本地直接跑；线上通过部署命令跑一次，随后改回正常启动）。

安全护栏：
1. `--keep` 不能为空 —— 否则会删光全部账号，没人能登录；
2. 保留账号中必须至少有一个具备「角色与权限配置」(account.role) 的账号，
   否则清理后无人能管理角色；
3. `--keep` 里拼错 / 不存在的账号会明确提示，避免"以为保留了、其实被删掉"；
4. 支持 `--dry-run`，先看清将删除的内容再决定是否执行。

关联引用的处理：`operation_log.user_id`、`metric_actual.created_by`、`task.created_by`
都指向账号。删除账号前先把这些引用置空 —— 保留操作日志与指标数据本身，
只解除指向已删账号的引用，避免留下悬空值。
"""
from __future__ import annotations

import argparse

from sqlalchemy import delete, func, select, update

from app.db.session import SessionLocal
from app.models import MetricActual, OperationLog, Role, Task, User


def _accounts_with_role_perm(db) -> set[str]:
    """具备「角色与权限配置」权限的角色，对应的账号集合。"""
    perms = {r.id: (r.permissions or []) for r in db.scalars(select(Role)).all()}
    return {
        u.account
        for u in db.scalars(select(User)).all()
        if "account.role" in perms.get(u.role_id, [])
    }


def purge(db, keep: list[str], *, tasks: bool = True, dry_run: bool = False) -> dict:
    keep = [a.strip() for a in keep if a and a.strip()]
    if not keep:
        raise SystemExit("拒绝执行：--keep 不能为空，否则会删光全部账号、无人可以登录。")

    keep_users = list(db.scalars(select(User).where(User.account.in_(keep))).all())
    kept = {u.account for u in keep_users}
    missing = [a for a in keep if a not in kept]
    if missing:
        print(f"  [注意] 以下账号不存在，未参与保留：{'、'.join(missing)}")

    if not (_accounts_with_role_perm(db) & kept):
        raise SystemExit(
            "拒绝执行：保留账号中没有具备「角色与权限配置」权限的账号，"
            "清理后将无人能管理角色与权限。"
        )

    targets = list(db.scalars(select(User).where(User.account.notin_(keep))).all())
    target_ids = [u.id for u in targets]
    task_total = db.scalar(select(func.count()).select_from(Task)) or 0
    log_total = (
        db.scalar(
            select(func.count()).select_from(OperationLog).where(OperationLog.user_id.in_(target_ids))
        )
        or 0
        if target_ids
        else 0
    )

    result = {
        "keep": sorted(kept),
        "removed_users": [{"id": u.id, "name": u.name, "account": u.account} for u in targets],
        "tasks": task_total,
        "unlinked_logs": log_total,
    }
    if dry_run:
        return result

    # 1) 先解除指向被删账号的引用（保留日志与指标数据本身）
    if target_ids:
        db.execute(
            update(OperationLog).where(OperationLog.user_id.in_(target_ids)).values(user_id=None)
        )
        db.execute(
            update(MetricActual)
            .where(MetricActual.created_by.in_(target_ids))
            .values(created_by=None)
        )
        db.execute(update(Task).where(Task.created_by.in_(target_ids)).values(created_by=None))

    # 2) 清空任务
    if tasks and task_total:
        db.execute(delete(Task))

    # 3) 删除账号
    if target_ids:
        db.execute(delete(User).where(User.id.in_(target_ids)))

    # 4) 留一条痕迹，便于日后追溯这次清理是谁、在什么时候做的
    db.add(
        OperationLog(
            user_id=keep_users[0].id if keep_users else None,
            action="purge",
            target_type="data",
            target_id=",".join(sorted(kept)),
            detail={
                "removedUsers": [u["account"] for u in result["removed_users"]],
                "removedTasks": task_total,
            },
        )
    )
    db.commit()
    return result


def _report(result: dict, dry_run: bool) -> None:
    mode = "预演（未落库）" if dry_run else "执行完成"
    print(f"[maintenance] {mode}")
    print(f"  保留账号：{'、'.join(result['keep'])}")
    print(f"  将删除账号 {len(result['removed_users'])} 个：")
    for u in result["removed_users"]:
        print(f"    - {u['id']} {u['name']}（{u['account']}）")
    print(f"  任务数据：{result['tasks']} 条" + ("（将全部删除）" if result["tasks"] else ""))
    print(f"  解除引用：operation_log {result['unlinked_logs']} 条 user_id 置空")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="合一重卡经营看板 · 数据维护工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("purge", help="按白名单清理账号，并清空任务数据")
    p.add_argument("--keep", required=True, help="要保留的账号名，逗号分隔（如 chenzm,huguohai）")
    p.add_argument("--no-tasks", action="store_true", help="保留任务数据，只清理账号")
    p.add_argument("--dry-run", action="store_true", help="只打印将删除的内容，不写入数据库")

    args = parser.parse_args(argv)

    if args.cmd == "purge":
        with SessionLocal() as db:
            result = purge(
                db,
                args.keep.split(","),
                tasks=not args.no_tasks,
                dry_run=args.dry_run,
            )
        _report(result, args.dry_run)


if __name__ == "__main__":
    main()
