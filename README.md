# 合一重卡生态经营看板 · 生产级系统

前后端分离的集团级经营看板系统，将原单文件 HTML 原型演进为可正式部署的生产级应用。

- **后端**：Python 3.13 + FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic + PostgreSQL 15
- **前端**：Vue 3 + TypeScript + Vite 6 + Tailwind CSS + Pinia + Vue Router
- **部署**：Docker Compose（PostgreSQL + API + Nginx Web）

## 目录结构

```
.
├── docs/               # SDD 规范文档（需求/设计/页面布局/任务清单/开发规则）
│   ├── proposal.md     # 产品需求文档（PRD）
│   ├── design.md       # 技术设计文档（前后端分离可部署方案）
│   ├── layouts/        # 逐页布局示意
│   ├── tasks.md        # 任务拆解清单
│   └── project_rules.md# AI 开发规则与编码规范
├── backend/            # FastAPI 后端服务
│   ├── app/            # 应用源码（models/schemas/services/api/core/db）
│   ├── alembic/        # 数据库迁移
│   ├── tests/          # pytest 单元 + 接口测试
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/           # Vue 3 前端应用
│   ├── src/            # 页面/组件/状态/API 层
│   ├── nginx.conf      # 生产 Nginx（静态资源 + API 反代）
│   └── Dockerfile
└── deploy/             # 一键部署编排
    ├── docker-compose.yml
    └── .env.example
```

## 快速开始

### 方式一：Docker 一键部署（生产推荐）

```bash
cd deploy
cp .env.example .env        # 修改 JWT_SECRET / 数据库密码
docker compose up -d --build
```

启动后访问 http://localhost:8080 。首次启动自动执行迁移并写入种子数据（AUTO_SEED=1）。

### 方式二：本地开发

**后端**（需 Python 3.13）：

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
DATABASE_URL="sqlite:///./dev.db" python -m app.seed      # 初始化种子数据
uvicorn app.main:app --reload --port 8000
```

**前端**（需 Node 22）：

```bash
cd frontend
npm install
npm run dev        # Vite 开发服务器，代理 /api 到 localhost:8000
```

### 方式三：单容器同源部署（一个端口）

把前端产物交给后端同源托管，无需 Nginx 与跨域配置：

```bash
cd frontend && npm run build && cp -R dist ../backend/static
cd ../backend && sh start.sh          # 读取 PORT（默认 3000），自动建表 + 种子数据
```

或直接用环境变量启动：

```bash
STATIC_DIR=./static uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`STATIC_DIR` 未设置或目录不存在时自动退化为纯 API 服务，不影响前后端分离部署。

## 换设备 / 迁移到另一台机器

在线分享链接是**公网地址，与本地源码无关**，直接浏览器打开即可访问，不需要源码、也不需要 WorkBuddy 在本机。

如果要在新设备上继续开发或重新发布，按下面步骤：

1. 把源码放到新设备（推荐用 `合一重卡经营看板-源码包.zip`，含完整 git 历史；或 `git clone` 后 checkout 到 `main`）。
2. **保持与本机一致的目录结构**：项目根目录为 `~/WorkBuddy/heyi-fleet-dashboard/`，其中发布目录是 `backend/`。发布工具是按「本地目录」匹配已有应用的，
   路径不同可能被识别为新应用并生成新链接；若只想更新现有链接，请沿用同一路径。
3. 恢复依赖并启动：

```bash
# 后端
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL="sqlite:///./dev.db" python -m app.seed
uvicorn app.main:app --port 8000

# 前端
cd ../frontend && npm install && npm run dev
```

4. 自检：`cd backend && pytest -q`（应为 49 passed）。

> WorkBuddy 的「发布的应用」卡片记录的是「哪个本地目录发布了该应用」。换设备后本机没有那个目录，会提示「找不到本地工程目录」——
> 这只影响本地预览与重新发布，**不影响已上线的分享链接**。

## 演示账号

种子数据内置 14 个账号，初始密码由 `SEED_PASSWORD` 控制（默认 `Demo#2026`）：

| 账号 | 姓名 | 角色 | 部门 |
|------|------|------|------|
| `chenzm` | 陈志明 | 系统管理员 | 全公司 |
| `linxue` | 林雪 | 部门负责人 | 市场部 |
| `wangjg` | 王建国 | 部门负责人 | 财务部 |
| `zhengkai` | 郑凯 | 成员 | 市场部 |
| `liqiang` | 李强 | 部门负责人 | 合一重卡运营公司(PC1) |

## 核心指标口径

- 完成率 = 累计完成 / 年度目标
- 回款率 = 累计回款 / 累计收入（目标 95%）
- 时间进度 = 年度进度（10 月 ≈ 77.8%）
- 红黄绿灯：正向指标达目标×95% 为绿、×90% 为黄、否则红；逆向/零目标按绝对值判定

## 功能模块

1. **经营驾驶舱** — 核心指标、监控指标、项目公司对比、部门任务完成度、风险与异常
2. **任务管理** — 一级/二级任务、超宽冻结列、导入导出
3. **指标维护** — 公司整体目标 / 指标监控 / 项目公司指标（列表化增删）
4. **账号管理** — 组织结构（全公司 + 11 部门）、账号、角色权限（菜单+按钮级 RBAC）

## 测试与文档

- 后端测试：`cd backend && pytest -q`（42 项通过）
- 接口文档：启动后访问 `http://localhost:8000/api/docs`
- 完整规范见 `docs/` 目录，部署细节见 `docs/design.md` §12

## 本机运行状态（迁移后）

| 入口 | 地址 | 说明 |
|------|------|------|
| 生产形态（推荐） | http://127.0.0.1:8000 | 后端同源托管前端构建产物，单端口即可访问 |
| 开发形态 | http://127.0.0.1:5173 | Vite 开发服务（热更新），`/api` 反向代理到 8000 |

启动命令：

```bash
# 后端（同源托管前端；先确保已执行 frontend 构建并拷入 backend/static）
cd backend && DATABASE_URL="sqlite:///./dev.db" STATIC_DIR=./static uvicorn app.main:app --port 8000

# 前端开发服务
cd frontend && npm run dev
```
