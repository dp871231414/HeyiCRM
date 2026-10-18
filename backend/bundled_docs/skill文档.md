# 车队经营看板 · Skill / Agent 协作文档

> 对象：负责本项目迭代的 AI Agent（含迁移到其他 Agent 工具时的接手说明）　|　最后更新：2026-10-18（Round 36）

---

## 1. 项目本质
- 单仓库全栈应用：后端 FastAPI + SQLAlchemy 2.0 + SQLite；前端 Vue3 + TS + Vite。
- 部署形态：单容器，`backend/` 为部署根，`start.sh` 负责 seed（幂等）+ 启动 Uvicorn（监听 `$PORT`、0.0.0.0）；前端构建产物须 `cp -R frontend/dist/. backend/static/` 后随后端一起部署。
- 默认账号 `admin / 123456`。

## 2. 本地环境
- Python 3.13 venv：`/Users/gavin/.workbuddy/binaries/python/envs/fleet/bin/python`（已装 markdown 等依赖）。
- Node 22：`/Users/gavin/.workbuddy/binaries/node/versions/22.22.2-6/bin/npm`。
- 后端测试：`cd backend && <venv>/python -m pytest -q`（当前 164+ 用例）。
- 前端构建：`cd frontend && npm run build`（含 `vue-tsc` 类型检查，零错误才通过）。

## 3. 迭代标准动作（强约束）
1. **改代码前**：先读相关视图/路由/服务，确认字段名与接口路径（勿凭记忆）。
2. **后端改动**：加模型 → 在 `models/__init__.py` 注册 → 加 schema → 加路由（`api/v1/*.py`，`prefix` 用 `/system/...` 之类，鉴权用 `require_perm`）。
3. **前端改动**：加路由（`router/index.ts` 的 `children`，`meta.perm` 与后端权限一致）→ 加菜单（`AppLayout.vue` 的 `ALL_MENUS`，硬编码）→ 加类型（`types/index.ts`）→ 加 API（`api/index.ts`）。菜单与路由是**两处独立改动**。
4. **测试**：后端 pytest 必绿；前端 build 必过；新增行为补用例。
5. **部署三步（缺一不可）**：`npm run build` → `cp -R frontend/dist/. backend/static/` → `workbuddy_sites_deploy`（`directory=backend/`，`startCmd=bash start.sh`）。
6. **线上验证**：登录拿 `Set-Cookie` 解析 `access_token` 随请求带 Cookie（**线上代理改写 Authorization，Bearer 失效**）；用临时数据验证后清理。验证脚本放 `backend/tools/verify_live_roundNN.py`。

## 4. 红线（用户明确，不可违反）
- **线下数据不自动同步生产**：仅发布代码与 seed 配置默认值；`start.sh` 不注入 `SEED_DEMO`，沙箱重建后库回到演示初态。线上验证用的临时数据必须删除，不污染生产。
- 已存在的**数据字典配置只允许启用/停用，不允许删除**。

## 5. 文档中心（Round 36 新增的「自动更新」机制）
- 文档源文件在 `docs/`：`产品需求文档.md` / `技术文档.md` / `测试文档.md` / `使用说明.html` / `设计文档.md` / `skill文档.md` / `项目开发说明.md`。
- 每次迭代：更新上述源文件 → 复制到 `backend/bundled_docs/` → 调 `POST /system/docs/sync` 写入 `system_doc` 表 → 前端「系统配置 → 使用说明」文档中心从库读取渲染。
- 这实现了需求 2/3 的「每次迭代自动更新产品需求/技术/测试文档」与需求 1 的「使用说明内容存库、每次迭代自动更新」。

## 6. 记忆纪律
- 每日工作日志落在 `.workbuddy/memory/YYYY-MM-DD.md`（append-only）。
- 跨项目/长期用户偏好在 `~/.workbuddy/user-.../MEMORY.md`（如「不要用警告词」「结果直接展示」）。
- 项目长期约定在 `.workbuddy/memory/MEMORY.md`。

## 7. 常见坑（已踩过）
- **Pydantic v2 `field_validator` 不校验被省略且有默认值的字段**：强制必填须去掉默认值或用 `model_validator(mode="after")`。
- **FastAPI 路由顺序**：静态路由（如 `GET /export`）须声明在动态路由（`GET /{id}`）之前。
- **漏斗 vs 可保存阶段**：漏斗阶段 `MARKET_STAGES`（不含流失 0）；可保存阶段 `ALL_PROJECT_STAGE_VALUES`（含 0）。新增阶段必须同步三处（白名单/标签映射/importer）。
- **预估消化取整**：用 `int(x+0.5)` half-up，而非内置 `round()` 的银行家舍入。
- **前端懒加载块校验**：验证线上前端字符串时，须从入口 chunk 沿动态 import 收集懒加载块再校验（只扫入口会漏）。

## 8. 迁移到其他 Agent 工具
- 见根目录 `README-迁移说明.md` 与压缩包结构：源码（排除 node_modules/.git/*.db）、`docs/`、`项目记忆/`。
- 接手 Agent 应先读 `docs/项目开发说明.md`（迭代史）+ `docs/技术文档.md`（架构）+ `docs/skill文档.md`（协作约定）。
