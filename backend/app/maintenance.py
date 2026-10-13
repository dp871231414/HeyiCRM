"""数据维护工具（一次性运维动作，不暴露为 HTTP 接口）。

用法：
    .venv/bin/python -m app.maintenance purge --keep admin,huguohai --dry-run
    .venv/bin/python -m app.maintenance purge --keep admin,huguohai
    .venv/bin/python -m app.maintenance rename --account chenzm --to admin --password 123456
    .venv/bin/python -m app.maintenance rename --account chenzm --to admin --dry-run

为什么不做成接口：
- 删除账号、清空任务都是**不可逆**动作，不需要在日常界面上暴露；
- 改账号名同理 —— 账号名是登录标识符，界面上刻意不提供修改入口
  （`UserUpdate` 里没有 account 字段），改名属于一次性运维动作。
需要时由运维显式执行一次即可（本地直接跑；线上通过部署命令跑一次，随后改回正常启动）。

安全护栏：
1. `purge --keep` 不能为空 —— 否则会删光全部账号，没人能登录；
2. `purge` 的保留账号中必须至少有一个具备「角色与权限配置」(account.role) 的账号，
   否则清理后无人能管理角色；
3. `purge --keep` 里拼错 / 不存在的账号会明确提示，避免"以为保留了、其实被删掉"；
4. `rename` 会校验新账号名格式与**唯一性**（已存在则拒绝，避免顶掉别人的账号），
   且要求目标账号存在；新密码长度与接口约束一致（6-128 位）；
5. 两者都支持 `--dry-run`，先看清将要发生什么再决定是否执行。

关联引用的处理：`operation_log.user_id`、`metric_actual.created_by`、`task.created_by`
都指向账号的 **id**（不是账号名），因此改名不会产生悬空引用；
而 purge 删除账号前会先把这些引用置空 —— 保留操作日志与指标数据本身，
只解除指向已删账号的引用，避免留下悬空值。
"""
from __future__ import annotations

import argparse
import re

from sqlalchemy import delete, func, select, update

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import MetricActual, OperationLog, Role, Task, User

# 与 schemas/user.py 的约束对齐：账号 2-32 位，密码 6-128 位
ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.-]{2,32}$")
PWD_MIN, PWD_MAX = 6, 128


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


def rename(
    db,
    account: str,
    new_account: str,
    *,
    password: str | None = None,
    dry_run: bool = False,
) -> dict:
    """把账号名从 `account` 改为 `new_account`，可选同时重置密码。

    账号名是登录标识符，界面上刻意不提供修改入口，改名属一次性运维动作。
    引用（operation_log / metric_actual / task 的 created_by）都存的是 **id**，
    所以改名不会产生悬空引用。
    """
    account = (account or "").strip()
    new_account = (new_account or "").strip()

    user = db.scalar(select(User).where(User.account == account))
    if not user:
        raise SystemExit(f"拒绝执行：账号「{account}」不存在。")

    if not ACCOUNT_RE.match(new_account):
        raise SystemExit(
            f"拒绝执行：新账号名「{new_account}」不合法（需 2-32 位的字母、数字、下划线、点或连字符）。"
        )

    renamed = new_account != account
    if renamed and db.scalar(select(User).where(User.account == new_account)):
        raise SystemExit(f"拒绝执行：账号「{new_account}」已存在，改名会顶掉现有账号。")

    if password is not None and not (PWD_MIN <= len(password) <= PWD_MAX):
        raise SystemExit(f"拒绝执行：新密码长度需在 {PWD_MIN}-{PWD_MAX} 位之间。")

    result = {
        "id": user.id,
        "name": user.name,
        "from": account,
        "to": new_account,
        "renamed": renamed,
        "password_reset": password is not None,
    }
    if dry_run:
        return result

    if renamed:
        user.account = new_account
    if password is not None:
        user.password_hash = hash_password(password)

    db.add(
        OperationLog(
            user_id=user.id,
            action="rename_account",
            target_type="user",
            target_id=user.id,
            detail={
                "from": account,
                "to": new_account,
                "passwordReset": password is not None,
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


def _report_rename(result: dict, dry_run: bool) -> None:
    mode = "预演（未落库）" if dry_run else "执行完成"
    print(f"[maintenance] {mode}")
    print(f"  账号：{result['id']} {result['name']}")
    if result["renamed"]:
        print(f"  改名：{result['from']} → {result['to']}")
    else:
        print(f"  账号名未变（{result['to']}）")
    print(f"  密码：{'已重置' if result['password_reset'] else '未变更'}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="合一重卡经营看板 · 数据维护工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("purge", help="按白名单清理账号，并清空任务数据")
    p.add_argument("--keep", required=True, help="要保留的账号名，逗号分隔（如 admin,huguohai）")
    p.add_argument("--no-tasks", action="store_true", help="保留任务数据，只清理账号")
    p.add_argument("--dry-run", action="store_true", help="只打印将删除的内容，不写入数据库")

    r = sub.add_parser("rename", help="重命名账号（可选同时重置密码）")
    r.add_argument("--account", required=True, help="现有账号名")
    r.add_argument("--to", required=True, dest="new_account", help="新的账号名")
    r.add_argument("--password", default=None, help="同时重置为该密码（不传则密码不变）")
    r.add_argument("--dry-run", action="store_true", help="只打印将要发生的变化，不写入数据库")

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

    elif args.cmd == "rename":
        with SessionLocal() as db:
            result = rename(
                db,
                args.account,
                args.new_account,
                password=args.password,
                dry_run=args.dry_run,
            )
        _report_rename(result, args.dry_run)


if __name__ == "__main__":
    main()
