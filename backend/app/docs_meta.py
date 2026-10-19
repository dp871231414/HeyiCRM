"""文档中心元信息：源文件映射与渲染工具。

部署时把 docs/ 下的最新文档复制到 backend/bundled_docs/，再调用
POST /system/docs/sync 即可把最新内容写入数据库，实现「每次迭代自动更新」。
"""
from __future__ import annotations

import os

# docs_meta.py 位于 backend/app/，BASE_DIR 即 backend/
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# 部署时由发布流程把 docs/ 复制到 backend/bundled_docs/
BUNDLED_DOCS_DIR = os.path.join(BASE_DIR, "bundled_docs")

# doc_key -> (源文件名, 格式: markdown | html)
DOC_BUNDLES: dict[str, tuple[str, str]] = {
    "usage": ("使用说明.html", "html"),
    "prd": ("产品需求文档.md", "markdown"),
    "tech": ("技术文档.md", "markdown"),
    "test": ("测试文档.md", "markdown"),
    "visual": ("视觉交互文档.md", "markdown"),
    "skill": ("skill文档.md", "markdown"),
    "devnotes": ("项目开发说明.md", "markdown"),
}
DOC_TITLES: dict[str, str] = {
    "usage": "使用说明",
    "prd": "产品需求文档",
    "tech": "技术文档",
    "test": "测试文档",
    "visual": "视觉交互文档",
    "skill": "Skill 文档",
    "devnotes": "项目开发说明",
}
DOC_ORDER: list[str] = ["usage", "prd", "tech", "test", "visual", "skill", "devnotes"]

# 每个内置文档归属的分组（与数据字典 doc_group 的取值一致）。
# 使用说明面向终端用户 -> 用户文档；其余为开发/实施文档 -> 开发文档。
# 用户新建文档未指定分组时默认「默认文档」，但内置文档的分组由 seed / sync 统一维护。
DOC_GROUPS: dict[str, str] = {
    "usage": "用户文档",
    "prd": "开发文档",
    "tech": "开发文档",
    "test": "开发文档",
    "visual": "开发文档",
    "skill": "开发文档",
    "devnotes": "开发文档",
}


def read_bundle(key: str) -> str | None:
    """读取 bundled_docs 中对应源文件；不存在返回 None。"""
    spec = DOC_BUNDLES.get(key)
    if not spec:
        return None
    path = os.path.join(BUNDLED_DOCS_DIR, spec[0])
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render_html(content: str, fmt: str) -> str:
    """把存储内容渲染为可安全 v-html 的 HTML。

    - html 格式：原样返回（已是自包含 HTML，前端用 iframe srcdoc 渲染）。
    - markdown 格式：用 markdown 库转 HTML（启用表格与围栏代码块）。
    """
    if fmt == "html":
        return content or ""
    try:
        import markdown

        return markdown.markdown(content or "", extensions=["tables", "fenced_code"])
    except Exception:
        return (content or "").replace("\n", "<br/>")
