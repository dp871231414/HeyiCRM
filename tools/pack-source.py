#!/usr/bin/env python3
"""打包源码交付包（给接手开发的人 / AI 代理）。

为什么不用 `zip` 命令：macOS 自带的 zip 不会把中文文件名按 UTF-8 写入，
在 Python / Windows / Linux 侧读出会变成乱码（实测 `交接说明.md` 会变成
`Σ║ñµÄÑΦ»┤µÿÄ.md`）。这里用 zipfile 显式写入 UTF-8 并打上 UTF-8 标志位（0x800）。

用法：
    python3 tools/pack-source.py                     # 输出到项目根的 合一重卡经营看板-源码包.zip
    python3 tools/pack-source.py /tmp/out.zip        # 指定输出路径
    python3 tools/pack-source.py --list-excluded     # 只打印排除规则
"""
from __future__ import annotations

import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "合一重卡经营看板-源码包.zip"
TOP_DIR = "heyi-fleet-dashboard"  # 包内顶层目录名（与本地工程目录保持一致）

# 目录名（任意层级）命中即整棵跳过
EXCLUDE_DIRS = {
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".pytest_cache",
    ".mypy_cache",
    ".npm-cache",
    ".vite",
    ".idea",
    ".vscode",
    "dist",  # 前端构建产物：已由 backend/static 提供，解压后可用 npm run build 重新生成
}

# 文件名后缀命中即跳过
EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",  # 本地数据库（含演示数据），接手方用 app.seed 初始化
    ".log",
    ".genie",
    ".zip",  # 避免把上一次的交付包打进去
}

# 文件名（精确）命中即跳过
EXCLUDE_FILES = {
    ".DS_Store",
    ".env",  # 只带 .env.example
    # WorkBuddy 内部映射（应用 locator / 资产库 id），对开发者无用
    "applications.yaml",
    "asset-upload-map.json",
    # 资产库上传清单：内部协作用，不属于工程
    "项目资产库-上传清单.md",
}


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
        return True
    if rel.name in EXCLUDE_FILES or path.suffix in EXCLUDE_SUFFIXES:
        return True
    if path.suffix in {".xlsx", ".xls", ".csv"} and "templates" not in rel.parts:
        # 导入模板由后端动态生成，不需要随包分发
        return True
    if path.name.endswith("源码包.zip") or path.name.endswith("交付包.zip"):
        return True
    # 允许保留 .env.example
    return False


def collect() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.relative_to(ROOT).parts[:-1]):
            continue
        if should_skip(path):
            continue
        files.append(path)
    return sorted(files)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--list-excluded" in sys.argv:
        print("排除目录：", ", ".join(sorted(EXCLUDE_DIRS)))
        print("排除后缀：", ", ".join(sorted(EXCLUDE_SUFFIXES)))
        print("排除文件：", ", ".join(sorted(EXCLUDE_FILES)))
        return 0

    out = Path(args[0]).expanduser().resolve() if args else DEFAULT_OUT
    files = collect()

    total_bytes = 0
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            rel = path.relative_to(ROOT)
            # 传入 str 时 zipfile 会按 UTF-8 编码并自动置位 0x800（跨平台可读）
            arcname = f"{TOP_DIR}/{rel.as_posix()}"
            zf.write(path, arcname)
            total_bytes += path.stat().st_size

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"已生成：{out}")
    print(f"  文件数：{len(files)}")
    print(f"  原始体积：{total_bytes / 1024 / 1024:.1f} MB → 压缩后：{size_mb:.1f} MB")
    print(f"  顶层目录：{TOP_DIR}/")
    print(f"  生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 自检：中文路径与 UTF-8 标志位
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        cn = [n for n in names if any("\u4e00" <= c <= "\u9fff" for c in n)]
        flagged = all(i.flag_bits & 0x800 for i in zf.infolist() if any("\u4e00" <= c <= "\u9fff" for c in i.filename))
        print(f"  中文路径 {len(cn)} 个，均带 UTF-8 标志：{'是' if flagged else '否 ❌'}")
        bad = zf.testzip()
        print(f"  完整性校验：{'正常' if bad is None else f'损坏于 {bad}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
