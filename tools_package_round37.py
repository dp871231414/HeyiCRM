"""Round 37 打包：生成两份 UTF-8 安全的 zip。

1) heyi-fleet-文档包.zip  —— 项目说明文件（docs/ 下 7 个文档）
2) heyi-fleet-源码包.zip   —— 最新源码（排除 DB / 依赖 / 构建产物 / 缓存）

使用 Python zipfile：自动以 UTF-8 存储文件名，规避 macOS `zip` 在中文名上的乱码。
"""
from __future__ import annotations

import os
import zipfile

ROOT = "/Users/gavin/WorkBuddy/heyi-fleet-dashboard"
OUT_DIR = os.path.join(ROOT, "发布包")
os.makedirs(OUT_DIR, exist_ok=True)

# ----- 文档包：docs/ 下 7 个文件 -----
DOC_FILES = [
    "产品需求文档.md",
    "技术文档.md",
    "测试文档.md",
    "视觉交互文档.md",
    "skill文档.md",
    "项目开发说明.md",
    "使用说明.html",
]
DOC_ZIP = os.path.join(OUT_DIR, "heyi-fleet-文档包.zip")

# ----- 源码包：排除项 -----
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".vite", ".idea", ".vscode",
    ".workbuddy", ".npm-cache", ".cache", "经营看板",
    "backend/static", "frontend/dist", "backend/downloads", "发布包",
}
EXCLUDE_SUFFIXES = (".db", ".pyc", ".pyo", ".log", ".zip")
EXCLUDE_BASENAMES = {".DS_Store"}
SRC_ZIP = os.path.join(OUT_DIR, "heyi-fleet-源码包.zip")


def in_exclude(path_rel: str) -> bool:
    parts = path_rel.split(os.sep)
    for p in parts:
        if p in EXCLUDE_DIRS:
            return True
    base = os.path.basename(path_rel)
    if base in EXCLUDE_BASENAMES or base.endswith(EXCLUDE_SUFFIXES):
        return True
    return False


def add_doc_package():
    with zipfile.ZipFile(DOC_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in DOC_FILES:
            src = os.path.join(ROOT, "docs", f)
            if not os.path.isfile(src):
                print(f"  [warn] 文档缺失：{f}")
                continue
            z.write(src, arcname=f)  # 平铺到包根，UTF-8 中文名
            print(f"  + {f}  ({os.path.getsize(src)} bytes)")
    print(f"文档包 -> {DOC_ZIP}  ({os.path.getsize(DOC_ZIP)} bytes)")


def add_source_package():
    n = 0
    with zipfile.ZipFile(SRC_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            # 原地剪枝排除目录
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS
                           and os.path.join(os.path.relpath(dirpath, ROOT), d) not in EXCLUDE_DIRS]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT)
                if in_exclude(rel):
                    continue
                z.write(full, arcname=rel)
                n += 1
    print(f"源码包 -> {SRC_ZIP}  ({os.path.getsize(SRC_ZIP)} bytes, {n} files)")


if __name__ == "__main__":
    print("=== Round 37 打包 ===")
    print("[1/2] 文档包：")
    add_doc_package()
    print("[2/2] 源码包：")
    add_source_package()
    print("完成。")
