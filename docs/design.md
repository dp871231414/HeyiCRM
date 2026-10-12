# 合一重卡生态经营看板 · 技术设计（design）

> 版本：v1.0 · 2026-10-10
> 上游：`docs/proposal.md`（需求编号 A/O/R/U/M/T/D/I）
> 说明：本文回答「用什么技术、模块如何协作、如何部署」。用户已锁定技术栈，本文严格遵守。

---

## 1. 技术选型及理由

| 层 | 选型 | 为什么选它 | 为什么不选其他 |
|---|---|---|---|
| 后端语言 | Python 3.11 | 团队熟悉；数据处理与算法（达成率、加权、导入校验）表达清晰；生态成熟 | 不选 Node：后端与现有 Python 运维体系不一致；不选 Go：开发效率对本项目收益不明显 |
| Web 框架 | FastAPI | 原生异步、自动生成 OpenAPI 文档、Pydantic v2 强校验降低接口脏数据 | 不选 Django：本项目无需重型 ORM/Admin，Django 偏重；不选 Flask：需自行拼装校验与文档 |
| ORM | SQLAlchemy 2.0（同步） | 2.0 声明式类型化、与 Alembic 迁移无缝；聚合可下推到 SQL | 不选裸 SQL：可维护性差；不选 Tortoise：生态小于 SQLAlchemy |
| 数据库 | PostgreSQL 15 | 强聚合与窗口函数（加权汇总、环比）、并发写入安全、JSONB 支持日志明细 | 不选 SQLite：并发写锁表、聚合能力弱；不选 MySQL：窗口函数与 JSONB 体验不及 PG |
| 迁移 | Alembic | 与 SQLAlchemy 同源，版本化 DDL，可回滚 | 不选手工建表：无法追溯 |
| 鉴权 | JWT（HttpOnly Cookie + Authorization 双支持） | 无状态，天然支持多实例水平扩展 | 不选服务端 Session：多实例需共享存储，复杂度更高 |
| 密码 | bcrypt（passlib） | 加盐哈希、抗暴力破解、无明文/可逆风险 | 不选 MD5/SHA1：不安全；不选明文：不可接受 |
| Excel | openpyxl | 读写模板、单元格校验、错误高亮均可实现 | 不选 pandas：重依赖，本项目是行级校验而非数据分析 |
| 前端框架 | Vue 3 + TypeScript | 组合式 API 便于按模块封装；TS 提供接口类型约束 | 不选 React：团队栈为 Vue；不选原生：生产级需路由/状态/构建 |
| 构建 | Vite | 秒级冷启动与 HMR；产物可静态托管 | 不选 Webpack：配置繁琐、构建慢 |
| 样式 | Tailwind CSS | 与原型设计令牌对齐，原子类便于保持一致性 | 不选组件库成品主题：需高度定制，改造成本高 |
| 状态 | Pinia | Vue 3 官方推荐，TS 友好 | 不选 Vuex：官方已推荐迁移 Pinia |
| HTTP | Axios | 拦截器统一处理令牌与错误 | 不选 fetch：需自行封装拦截与错误规范 |
| 部署 | Docker Compose（PG + API + Nginx 静态前端 + 反向代理） | 一键起全栈，环境一致；上云只需换镜像仓库与编排 | 不选裸机脚本：环境漂移；不选 K8s：一期规模无需 |
| 反向代理 | Nginx | 静态托管 + 反代 API + 统一入口，规避跨域 | 不选 CORS 直连：生产环境更希望同源 |

---

## 2. 总体架构

```
                          ┌─────────────────────────────────────────┐
   浏览器  ────────────────▶│  Nginx (80/443)                         │
   (Vue SPA)               │   ├─ /            → 前端静态产物 (dist)   │
                          │   └─ /api/        → 反代 backend:8000    │
                          └─────────────────────────────────────────┘
                                             │
                                             ▼
                          ┌─────────────────────────────────────────┐
                          │  FastAPI (Uvicorn, 可多实例)             │
                          │   API 层  /api/v1/*                      │
                          │   ├─ auth / orgs / projects              │
                          │   ├─ users / roles                       │
                          │   ├─ metrics / tasks / dashboard         │
                          │   └─ deps: JWT 鉴权 + 权限/范围依赖       │
                          │   Service 层（业务纯逻辑）                │
                          │   ├─ achievement 达成率/红黄绿灯/回款     │
                          │   ├─ summary     规则生成分析总结         │
                          │   ├─ scope       可见范围（组织/任务）    │
                          │   └─ importer    Excel 解析 + 逐行校验    │
                          │   Model 层（SQLAlchemy 2.0）             │
                          └─────────────────────────────────────────┘
                                             │
                                             ▼
                          ┌─────────────────────────────────────────┐
                          │  PostgreSQL 15                           │
                          │   organization / metric_def /            │
                          │   metric_target / metric_actual /        │
                          │   task / user / role / operation_log     │
                          └─────────────────────────────────────────┘
```

**分层与边界**：API 层只做参数解析、鉴权、调用 Service、组装响应；Service 层为纯业务逻辑（可单测、与框架无关）；Model 层只管持久化。**聚合计算下推到 SQL**（`GROUP BY` / 窗口函数），禁止把上千行拉到 Python 循环。

---

## 3. 模块划分与职责

| 模块 | 职责 | 对外接口 | 依赖 |
|---|---|---|---|
| `core/security` | 密码哈希、JWT 签发与校验 | `hash_password` / `verify_password` / `create_token` / `decode_token` | 无 |
| `core/deps` | FastAPI 依赖：当前用户、权限校验、范围校验 | `get_current_user` / `require_perm(key)` | security, models |
| `services/achievement` | 达成率、红黄绿灯、回款率、时间进度、加权 | `calc_achievement` / `light_of` / `collection_rate` | models |
| `services/scope` | 依据角色/账号范围返回可见组织与任务 | `visible_org_ids` / `visible_task_filter` | models |
| `services/summary` | 规则生成分析总结（结论/亮点/风险/建议） | `build_summary` | achievement, scope |
| `services/importer` | Excel 模板定义、解析、逐行校验、入库 | `parse_task_rows` / `validate_*` / `import_*` | models |
| `api/v1/*` | 路由 | REST | 全部 service |
| `models/*` | ORM 表 | — | db |
| `seed` | 初始化组织/指标/角色/演示账号 | CLI | models |

---

## 4. 端到端数据流

**示例：部门负责人录入「运力收入」完成值**

```
① 前端 MetricsView 输入 21230 → 点保存
② PUT /api/v1/metrics/actuals  body={metric_id:"REV_TRANS", org_id:"CO", period:"2026-10", value:21230}
③ deps.get_current_user → 解析 JWT 得到 user
④ deps.require_perm("metric.edit") → 校验按钮权限
⑤ service.scope.visible_org_ids(user) → 校验 org_id ∈ 可见范围，否则 403
⑥ upsert metric_actual（唯一键 metric_id+period+org_id），写 operation_log
⑦ 返回 200 {ok:true}
⑧ 前端失效并重新拉取 GET /dashboard/overview?period=2026-10&org_id=CO
⑨ dashboard 服务在 SQL 层聚合 → 计算完成率/红黄绿灯/加权 → 组装卡片
⑩ 页面刷新，读数与维护页同源一致
```

**示例：管理员导入任务 Excel**

```
① 前端上传文件 → POST /api/v1/tasks/import (multipart)
② importer 读取工作簿 → 定位「任务数据」表头 → 逐行解析为 dict
③ validate_task_rows 逐行校验（8 类规则）→ 得到 errors[]
④ 有错误：返回 200 {imported:0, errors:[{row,field,msg}]}，错误行号回传前端高亮
⑤ 无错误：批量插入；一级任务相同的多行归组（first(parent).id 作为分组键）
⑥ 写 operation_log，返回 {imported:N}
```

---

## 5. 核心数据结构

### 5.1 `organization` 组织

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | varchar(16) | PK | CO / D01…D11 / PC1…PCn |
| name | varchar(64) | unique | 组织名称 |
| type | varchar(16) | not null | company / dept / team / project |
| parent_id | varchar(16) | FK self, nullable | 上级组织 |
| head | varchar(32) | | 负责人姓名 |
| sort_order | int | default 0 | 展示顺序 |
| created_at / updated_at | timestamptz | | 审计字段 |

> 项目公司 `type=project`，`parent_id=CO`，不参与组织树下拉（`deptTree` 排除 project）。

### 5.2 `metric_def` 指标定义

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(32) PK | 指标编码 REV_SALE / COLL_* / OP_* / INC_* … |
| name | varchar(64) | 指标名称 |
| unit | varchar(16) | 单位 |
| group | varchar(16) | annual / project / monitor |
| family | varchar(24) | revenue / collection / digest / op / incident / fault / rent |
| parent_id | varchar(32) FK self | 回款子指标指向主指标 |
| direction | varchar(8) | positive / negative |
| cycle | varchar(8) | month / quarter / year |
| weight | int | 加权（回款子指标为 0） |
| warn | numeric(6,4) | 黄灯阈值（正向=目标倍数下限；逆向=允许超出倍数） |
| danger | numeric(6,4) | 红灯阈值/容忍上限 |
| rate_target | numeric(6,4) | 回款率目标（默认 0.95） |
| is_snapshot | bool | 期末快照（OP_VEH=true，非累计） |
| no_target | bool | 监控指标无目标 |
| owner_org_id | varchar(16) FK | 责任部门 |
| description | text | 口径说明 |
| sort_order | int | 展示顺序 |

**阈值语义约定（避免歧义）**
- 正向：`warn=0.95` → 实际值 ≥ 目标×0.95 仍为黄灯
- 逆向：`danger=1.1` → 实际值 ≤ 目标×1.1 仍为黄灯
- 目标为 0 的指标一律按绝对值判定

### 5.3 `metric_target` 目标值

| 字段 | 类型 | 约束 |
|---|---|---|
| id | bigserial PK | |
| metric_id | varchar(32) FK | |
| org_id | varchar(16) FK | |
| period | varchar(8) | 年度目标存 `'2026'`；月度指标存 `'2026-10'` |
| value | numeric(18,2) | |
| | | unique(metric_id, org_id, period) |

### 5.4 `metric_actual` 实际值

| 字段 | 类型 | 约束 |
|---|---|---|
| id | bigserial PK | |
| metric_id / org_id / period | | unique 同上 |
| value | numeric(18,2) | |
| created_by | varchar(16) FK user | |
| updated_at | timestamptz | 录入即生效，无审核状态字段 |

### 5.5 `task` 重点任务

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(32) PK | 任务ID，T202601… |
| parent | varchar(128) | 一级任务（任务名称） |
| title | varchar(128) nullable | 二级任务（任务分类），可空 |
| description | text | 任务描述 |
| abnormal | bool | 人工异常标记，默认 false |
| target | numeric(18,2) | 目标，非量化填 1 |
| done | numeric(18,2) | 已完成，非量化未完成 0 / 完成 1 |
| unit | varchar(16) | 数量单位，仅展示 |
| note | text | 进展描述 |
| start_date / end_date | date | 计划起止 |
| dept_id | varchar(16) FK | 责任部门 |
| owner | varchar(32) | 责任人姓名 |
| created_by / created_at / updated_at | | 审计 |

**计算列（不落库）**
```
完成进度 = round(done / target × 100)                    # target ≤ 0 → 0
剩余天数 = end_date − today
  未完成(done<target)：剩余<0 → 逾期N天；0≤剩余<1 → 临期；否则正常
  已完成(done≥target)  → 已完成（不再判逾期）
健康度 = 时间判定 ⊕ 人工异常标记（abnormal 且未完成 → 异常）
```

### 5.6 `user` / `role`

`role`：id(PK) / name(unique) / description / scope(self|dept|dept_sub|all) / is_system(bool) / permissions(jsonb: string[])

`user`：id(PK) / name / account(unique) / password_hash / dept_id(FK) / role_id(FK) / scope(nullable，覆盖角色默认) / status(active|disabled) / last_login_at / last_login_ip / created_at

**权限清单（代码常量 `PERM_GROUPS`，与前端共用一套 key）**

| 菜单 | 权限 key（menu） | 按钮权限 key（action） |
|---|---|---|
| 经营驾驶舱 | dashboard.view | — |
| 任务管理 | task.view | task.edit / task.delete / task.import |
| 指标维护 | metric.view | metric.edit / metric.import |
| 账号管理 | account.view | account.edit / account.role |

### 5.7 `operation_log` 操作日志

`id(bigserial) / user_id / action(varchar) / target_type / target_id / detail(jsonb) / ip / created_at`

---

## 6. 关键接口设计

统一前缀 `/api/v1`。统一响应：成功 `{ "data": ... }`；错误 `{ "detail": "…", "code": "…" }`。
状态码：200 成功 / 201 创建 / 400 参数错误 / 401 未登录 / 403 无权限 / 404 不存在 / 409 冲突（重名等） / 422 校验失败 / 500 服务异常。

### 6.1 鉴权

| 方法 | 路径 | 入参 | 出参 |
|---|---|---|---|
| POST | `/auth/login` | `{account, password}` | `{access_token, user, perms[], scope}` |
| POST | `/auth/logout` | — | `{ok:true}` |
| GET | `/auth/me` | — | `{user, perms[], scope}` |

### 6.2 组织与项目公司

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/orgs?flat=0` | 组织树（含 depth）；`flat=1` 返回扁平列表 |
| POST | `/orgs` | `{name, type, parent_id, head}` → 新增部门；重名 409 |
| PATCH | `/orgs/{id}` | 改名 / 改负责人 |
| DELETE | `/orgs/{id}` | 有账号或有子部门 → 409 并带原因 |
| GET | `/orgs/{id}/impact` | `{users, children, tasks}` 删除影响面 |
| GET | `/projects` | 项目公司列表（含负责人、指标影响面） |
| POST | `/projects` | `{name, head, targets:[{metric_id, value, year}]}` → 新增，返回新 id |
| PATCH | `/projects/{id}` | 改名 / 改负责人 |
| DELETE | `/projects/{id}` | 连带清理目标/完成值/任务，停用关联账号 |
| GET | `/projects/{id}/impact` | 删除影响面 |

### 6.3 角色与账号

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/permissions` | 权限清单（PERM_GROUPS）与范围选项（SCOPES），供角色编辑界面渲染 |
| GET | `/roles` | 角色列表（含账号数） |
| POST | `/roles` | 新增角色 |
| PATCH | `/roles/{id}` | 编辑名称/说明/范围/权限 |
| DELETE | `/roles/{id}` | 内置或有关联账号 → 409 |
| GET | `/users?keyword=&dept_id=&status=` | 账号列表 |
| POST | `/users` | 新增账号（初始密码必填） |
| PATCH | `/users/{id}` | 编辑；`scope` 传空串表示删除覆盖值（跟随角色） |
| POST | `/users/{id}/status` | `{status:"active"\|"disabled"}` 启停用 |

### 6.4 指标

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/metrics/defs?group=` | 指标定义（含权重、方向、口径） |
| GET | `/metrics/periods` | 可用周期列表与当前周期、数据截至日 |
| GET | `/metrics/board?period=&org_id=` | **维护页一次性数据**：三模块（annual/monitor/project）各自的指标行、目标、完成值、回款、完成率、状态、时间进度 |
| PUT | `/metrics/targets` | `{metric_id, org_id, period, value}` upsert；年度类自动换算为年份周期 |
| PUT | `/metrics/actuals` | 同上 |
| GET | `/metrics/import/template` | 下载指标导入模板（xlsx） |
| POST | `/metrics/import` | multipart 上传，返回 `{imported, errors[]}` |

### 6.5 任务

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/tasks?keyword=&dept_id=&status=&page=&size=` | 列表（服务端按可见范围过滤） |
| GET | `/tasks/{id}` | 详情 |
| POST | `/tasks` | 新建（自动生成任务ID） |
| PATCH | `/tasks/{id}` | 编辑 |
| DELETE | `/tasks/{id}` | 删除（需 task.delete 权限） |
| GET | `/tasks/dept-stats?period=` | 部门任务完成度聚合（SQL GROUP BY） |
| GET | `/tasks/import/template` | 下载任务导入模板 |
| POST | `/tasks/import` | multipart，返回 `{imported, errors[]}` |
| GET | `/tasks/export` | 导出当前可见任务 xlsx |

### 6.6 驾驶舱

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/dashboard/summary?period=&org_id=` | `{headline, tone, weighted, timeProgress, vsTime, counts, wins[], risks[], points[]}` |
| GET | `/dashboard/overview?period=&org_id=` | `{annual[], project[], monitor[], projectCompare[], deptTaskStats[]}` |
| GET | `/dashboard/metrics/{id}/trend?org_id=` | 该指标历史各期实际值（用于下钻趋势） |

**错误码约定**：`UNAUTHORIZED` `FORBIDDEN` `NOT_FOUND` `NAME_CONFLICT` `DELETE_BLOCKED` `IMPORT_INVALID` `PERIOD_MISMATCH`。

---

## 7. 状态流转

**登录态**：未登录 →（登录成功）→ 已登录 →（令牌过期/登出）→ 未登录。前端 401 拦截器统一跳转登录页。

**账号**：active ⇄ disabled（disabled 不可登录）。

**任务**（由数据推导，无手工状态字段）：
```
未完成 ─┬─ 剩余<0        → 逾期
        ├─ 0≤剩余<1      → 临期
        └─ 剩余≥1        → 正常
           （叠加 abnormal → 异常）
已完成（done≥target）→ 已完成（终态）
```

**指标**：无目标值（监控）→ 不参与判定；有目标无实际 → 未录入；有目标有实际 → 绿/黄/红。

---

## 8. 错误处理

| 分类 | 场景 | 处理 |
|---|---|---|
| 可重试 | 网络抖动、超时 | 前端提示「网络异常，请重试」，保留用户输入 |
| 不可重试 | 401/403/409/422 | 401 跳登录；403 提示无权限；409/422 展示服务端消息 |
| 降级 | 聚合接口超时 | 返回已缓存的上一次结果并标注时间；前端显示「数据可能不是最新」 |
| 数据 | 除零（目标 0 / 收入 0） | 达成率/回款率返回 `null`，前端显示「—」 |
| 导入 | 存在错误行 | 全量校验后统一返回错误明细，不写脏数据 |

---

## 9. 权限、安全与隐私

- **最小权限**：菜单权限控制入口可见性，按钮权限控制操作；服务端为最终裁决（`require_perm`）。
- **数据隔离**：`visible_org_ids(user)` 依据 `effective_scope` 计算；所有列表接口强制注入范围过滤，禁止前端传参绕过。
- **可见任务**：`任务所属组织 ∈ 可见组织` **OR** `责任人 = 本人姓名`（兜底规则，解决任务挂上级部门而责任人属下级的情况）。
- **密码**：bcrypt 加盐哈希；接口与日志均不返回 `password_hash`。
- **令牌**：JWT（HS256），密钥走环境变量；有效期默认 12 小时；支持 Authorization Bearer 与 HttpOnly Cookie。
- **审计**：登录、录入、修改、删除、导入写 `operation_log`（含 IP）。
- **配置**：数据库连接、JWT 密钥、CORS 白名单等全部环境变量外置，代码零硬编码。
- **越权防护**：前端隐藏按钮不作为安全边界；所有写接口二次校验权限与数据归属。

---

## 10. 性能考虑与降级方案

| 关注点 | 措施 |
|---|---|
| 聚合性能 | 驾驶舱加权汇总、部门任务完成度在 SQL 层 `GROUP BY`/窗口函数完成 |
| 索引 | `metric_actual(metric_id, org_id, period)` 唯一索引；`task(dept_id, end_date)`；`user(dept_id)` |
| N+1 | 指标行一次查询取回定义 + 目标 + 实际，避免逐行查询 |
| 前端 | 路由懒加载；驾驶舱数据一次请求返回；表格前端分页 + 服务端分页双支持 |
| 降级 | 聚合接口超时返回上次缓存并标注；导入大文件限制 5MB、单次 ≤ 2000 行 |
| 扩展 | 鉴权无状态，API 可水平扩容；数据库连接池（默认 20） |

---

## 11. 目录结构

```
.
├── docs/                        # 规范文档（本目录）
│   ├── proposal.md  design.md  tasks.md  project_rules.md
│   └── layouts/                 # 每页一个布局文件
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 环境变量配置
│   │   ├── db/{base,session}.py
│   │   ├── core/{security,deps}.py
│   │   ├── models/              # 8 张表 ORM
│   │   ├── schemas/             # Pydantic v2
│   │   ├── services/            # achievement/scope/summary/importer
│   │   ├── api/v1/              # auth/orgs/projects/roles/users/metrics/tasks/dashboard
│   │   └── seed.py
│   ├── alembic/                 # 迁移
│   ├── tests/                   # pytest
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                 # axios 封装 + 各模块接口
│   │   ├── stores/              # pinia auth/app
│   │   ├── router/              # 路由 + 权限守卫
│   │   ├── layouts/             # 外壳（侧边栏 + 顶栏）
│   │   ├── views/               # Login/Dashboard/Tasks/Metrics/Accounts
│   │   ├── components/          # 通用组件
│   │   ├── styles/              # 设计令牌 + Tailwind
│   │   ├── types/               # TS 类型（与后端 schema 对齐）
│   │   ├── App.vue  main.ts
│   ├── index.html  vite.config.ts  tailwind.config.js  tsconfig.json
│   └── Dockerfile
├── deploy/
│   ├── docker-compose.yml       # PG + API + Web + Nginx
│   ├── nginx.conf
│   └── .env.example
└── README.md                    # 总览 + 部署手册
```

---

## 12. 需求-方案对应关系

| 需求编号 | 承担模块 | 设计章节 |
|---|---|---|
| A-1 ~ A-4 登录与会话 | `api/v1/auth`, `core/security`, `core/deps` | §6.1, §7, §9 |
| O-1 ~ O-5 组织管理 | `api/v1/orgs`, `services/scope` | §5.1, §6.2 |
| R-1 ~ R-4 角色权限 | `api/v1/roles`, `PERM_GROUPS` 常量 | §5.6, §6.3, §9 |
| U-1 ~ U-5 账号管理 | `api/v1/users` | §5.6, §6.3, §9 |
| M-1 ~ M-12 指标维护 | `api/v1/metrics`, `services/achievement`, `services/importer` | §5.2–5.4, §6.4, §8 |
| T-1 ~ T-8 任务管理 | `api/v1/tasks`, `services/importer` | §5.5, §6.5, §7 |
| D-1 ~ D-8 经营驾驶舱 | `api/v1/dashboard`, `services/summary`, `services/achievement` | §4, §5.2, §6.6, §10 |
| I-1 ~ I-4 数据导入 | `services/importer` | §4, §6.4–6.5, §8 |

**MVP 与后续预留边界**：本期实现 proposal §5 全部功能；预留但不在本期实现的是——云对象存储切换（`storage` 抽象）、多实例水平扩容（鉴权已无状态）、指标版本回滚（数据结构已支持按周期留痕）。

---

## 13. 变更记录

### 13.1 2026-10-12 · 第二批变更

#### 统计周期（M-13）

| 文件 | 变更 |
|---|---|
| `frontend/src/constants/period.ts` | **新增**。`MONTH_MIN='2026-09'`、`MONTH_MAX='2099-12'`、`clampMonth()`、`listMonths()` —— 可选范围口径的唯一来源 |
| `frontend/src/components/MonthPicker.vue` | **新增**。原生 `<input type="month">` + `min`/`max` 约束 + 越界收敛 |
| `frontend/src/stores/view.ts` | `setPeriods(list, current, asOf)` → `setPeriods(current, asOf)`：不再用「有数据的月份」生成下拉；新增 `setPeriod(value)` 做范围收敛 |
| `frontend/src/layouts/AppLayout.vue` | 移除顶栏选择器与已无用的 `periods` 状态 |
| `views/DashboardView.vue`、`views/MetricsView.vue` | 页内引入 MonthPicker；任务管理页不引入 |

#### 指标口径（M-14）

语义未变（实际值本就按月存储"截止当月累计"），本轮为**命名与说明对齐**：

- 口径注释：`services/achievement.py`、`api/v1/metrics.py` 模块注释
- 元数据：`constants.METRIC_GROUP_META` 的 `annual` / `project` 描述
- 种子描述：`seed.py` 中回款类指标的 `description`
- 前端文案：表头「完成值」→「累计完成值」、项目公司列「完成」→「累计完成」、说明条改为"累计完成值为「截止当月」的累计值"；驾驶舱同步

#### 任务字段与模板（T-9 / I-5 / I-6）

| 文件 | 变更 |
|---|---|
| `services/achievement.py` | `task_to_dict` 新增 `createdById`（模型本已有 `created_at`/`updated_at`，本轮一并暴露） |
| `schemas/task.py` | `TaskOut` 新增 `createdById`/`createdByName`/`createdAt`/`updatedAt`；`TaskCreate`/`TaskUpdate` **不含**这些字段，前端传入会被忽略 |
| `api/v1/tasks.py` | 新增 `_enrich(db, items)` 批量补齐 `deptName` 与 `createdByName`（去重缓存，避免 N+1），替换原先 4 处逐条赋值；导入列名改为复用 `TASK_COLUMNS`；导出改为 `export_tasks(db, rows)` |
| `services/importer.py` | 列定义重命名并补 `数量单位`；新增 `TASK_OPTIONAL_COLUMNS`、`TASK_EXPORT_COLUMNS`；`parse_rows(..., optional=)` + `_locate_header_row()` 表头自动定位；新增样式层 `_write_banner`/`_style_header`/`_style_data_rows`/`_notes_sheet` |
| `views/TasksView.vue` | 新增「创建人」列（`COL_COUNT` 13 → 14，表宽同步） |

**模板列对照**

| 位置 | 列 |
|---|---|
| 导入模板（12 业务列） | 任务名称、任务分类、任务描述、是否异常、目标、已完成、数量单位、进展描述、计划开始日期、计划结束日期、责任部门、责任人 |
| 导出文件（18 列） | 任务ID + 上述 12 列 + 完成进度、状态、创建人、创建时间、更新时间 |
| 列表展示（14 列） | 任务ID、任务名称、任务分类、责任人、责任部门、创建人、目标、已完成、完成进度、计划起止、创建时间、更新时间、状态、操作 |

**模板样式规范**

| 位置 | 样式 |
|---|---|
| 第 1 行（说明栏标题） | 整行合并，浅蓝底 `DEEBF7`，深蓝 `1F4E79` 13号加粗，行高 28 |
| 第 2 行（操作提示） | 整行合并，浅蓝底，灰蓝 `5B6B7C` 9号 |
| 第 3 行 | 留白，行高 6 |
| 第 4 行（字段名称栏） | 主蓝底 `2E75B6`，白字加粗，居中换行，深蓝细边框，行高 24；**冻结窗格 `A5`** |
| 第 5 行起 | 数据区，淡蓝细边框 `BDD7EE`；示例行（仅模板）用极浅蓝 `F7FBFF` 弱化 |
| 其他工作表 | 「填写说明」「组织清单」「账号清单」「指标清单」共用同一套蓝色表头样式 |

**两处实现要点（易踩坑）**

1. **表头不固定在第 1 行**：模板顶部有说明栏，因此 `parse_rows` 改为在首 8 行内扫描「命中列名最多」的一行作为表头，同时兼容无说明栏的老模板。
2. **`freeze_panes` 不能用 `ws.cell()` 定位**：`ws.cell(row=5, column=1)` 会**创建**一个空单元格，使 `ws.append` 从第 6 行开始，模板里平白多出一行空白。必须用字符串 `ws.freeze_panes = "A5"`。

#### 指标维护入口下线（M-15）

- `views/MetricsView.vue`：移除「下载模板」「批量导入」按钮、导入结果弹窗、`onImport()`、`importOpen`/`importResult` 状态，以及 `downloadFile`/`ImportResult` 引用。
- 后端 `/metrics/import/template`、`/metrics/import` **保留**，仍受 `metric.import` 权限保护，供 API 直接调用。

### 13.2 2026-10-12 · 移除 Google Fonts 外链

**问题**：`index.html` 通过 `<link rel="stylesheet">` 引入 Google Fonts 的 Plus Jakarta Sans。
该域名国内访问不稳定，实测本地与线上均出现 `ERR_TIMED_OUT`；而 `<link rel="stylesheet">`
**属于渲染阻塞资源**，浏览器要等它失败（数秒）才开始首屏渲染。

**判断依据**：Plus Jakarta Sans 是**纯拉丁字体，不含中文字形**。浏览器按字符逐字回退，
页面中文**本来就**由 `PingFang SC` / `Microsoft YaHei` 渲染，该字体只影响英文字母与数字。

**改动**

| 文件 | 变更 |
|---|---|
| `frontend/index.html` | 删除 3 个 `<link>`（2 个 `preconnect` + 1 个样式表），留注释说明原因 |
| `frontend/tailwind.config.js` | `fontFamily.sans` 移除 `'Plus Jakarta Sans'`，改为纯系统字体栈 |
| `项目入口.html` | 本地启动台同步改为系统字体栈（一致性） |

**字体栈（现）**：`-apple-system` → `BlinkMacSystemFont` → `PingFang SC` → `Microsoft YaHei` → `Segoe UI` → `sans-serif`

**验证**（`tools/verify-no-external-font.mjs`）

| 项 | 结果 |
|---|---|
| 外部请求 | 0 个 |
| 字体文件请求 | 0 个（全走系统字体） |
| 控制台错误 | 0 个（此前为 `ERR_TIMED_OUT`） |
| `load` 事件耗时 | 77 ms |

**若日后需要跨机器一致的字体观感**：不要改回外链，改为**自托管** —— 下载 woff2 放入
`frontend/public/fonts/`，用 `@font-face` 引入（只需 latin 子集，约 80–100 KB），
可同时保留外观与零外链。

### 13.3 2026-10-12 · 演示数据重置开关（SEED_RESET）

为「把环境恢复到初始状态」提供一个**显式、可控**的入口，而不是每次启动都清库。

| 启动方式 | 行为 |
|---|---|
| `sh start.sh`（默认） | 幂等补齐：已有数据不动，仅新增缺失项、对齐内置角色权限 |
| `SEED_RESET=1 sh start.sh` | 先清空业务表（日志/指标值/目标/任务/账号/角色/指标定义/组织）再重新灌入，回到初始状态 |

**用法**：需要重置时，以 `SEED_RESET=1 sh start.sh` 作为启动命令部署一次，随后改回 `sh start.sh` 正常启动即可。
本项目的线上发布即按此方式执行过一次。

**初始状态**（重置后的基线）：

| 表 | 行数 |
|---|---|
| `organization` | 15（全公司 + 11 部门 + 3 项目公司） |
| `metric_def` | 24 |
| `metric_actual` | 224 |
| `metric_target` | 15 |
| `task` | 14 |
| `role` | 3（均为内置） |
| `user` | 14（U001–U014） |
| `operation_log` | 0 |

> 注意：`operation_log` 记录真实操作，登录一次即产生一条。若要求"完全零日志"的展示状态，
> 应在**最后一次**登录验证之后再执行重置。

### 13.4 2026-10-12 · 月份选择组件重做与项目公司权限点

#### 统计周期组件（M-16）

原实现是 `<input type="month">`，Safari 不支持该类型（退化为文本框），且 73 年跨度下只能逐月切换。
重做为**自绘面板**，不引入任何第三方库（前端依赖仍只有 vue / vue-router / pinia / axios）。

| 文件 | 变更 |
|---|---|
| `components/MonthPicker.vue` | **重写**。触发器（图标 + `YYYY年M月` + 箭头）+ 弹出面板 |
| `styles/main.css` | 新增 `.picker-nav`（面板翻页按钮） |

**组件结构**

| 部分 | 说明 |
|---|---|
| 触发器 | `button[aria-haspopup="dialog"]`，显示当前选中月份；展开时高亮并旋转箭头 |
| 面板（月模式） | 头部 `‹ 2026年 ›`，下方 3×4 月份网格 |
| 面板（年模式） | 点年份标题切换；头部 `‹ 2026-2037 ›`，按 **12 年**分页的年份网格 |
| 页脚 | 标注可选范围 `2026-09 ~ 2099-12` 与操作提示 |

**交互细节**

- 选中态：主色填充（`bg-brand-600` + 白字）；「本月」用描边标记（仅当落在可选范围内）
- 越界禁用：低于 `2026-09` 的月份、高于 `2099-12` 的月份，以及 2100 年起的年份，均为 `disabled`
- 年份分页与下界对齐：`MIN_Y + floor((year - MIN_Y) / 12) * 12`，最后一页含越界年份（已禁用），
  保证 2099 可达
- 关闭：点击面板外部（`document` 上的 `mousedown`）或按 `Esc`；关闭后焦点回到触发器
- 翻页游标 `viewYear` 与选中值解耦——翻页不会立刻改动选中周期

> **为什么必须做年份跳转**：范围是 2026-09 ~ 2099-12，共 73 年。若只按年翻页，
> 从默认年份到 2099 需点击 73 次，实际不可用。主流组件（如 antd / Element Plus）在
> 年份跨度大时同样提供年份面板，这里按 12 年一页实现。

#### 项目公司权限点（M-17）

| 文件 | 变更 |
|---|---|
| `constants.py` | 指标维护分组新增 `project.create` / `project.edit` / `project.delete` |
| `seed.py` | 系统管理员补齐三个权限点（其余角色默认不授予，可由管理员在界面勾选） |
| `api/v1/projects.py` | 三个接口分别改用 `require_perm("project.create/edit/delete")`；`update`/`delete` 增加 `org_in_scope` 兜底 |
| `views/MetricsView.vue` | 按钮显隐改为 `auth.hasPerm('project.create'/'project.edit'/'project.delete')`，不再依赖 `board.canEditAll` |

**权限模型的分工**（沿用既有约定）：

- **权限点**决定「能不能做」——与角色标识、当前视角无关；
- **可见范围**兜底「能作用于哪些对象」——否则持权限者可操作自己看不到的组织；
- 指标的编辑范围（`metric.edit_company` / `metric.edit_project`）与项目公司的增删改是两组独立权限，
  可以只给其一。

#### 删除项目公司的数据一致性

原实现只把关联账号置为 `disabled`，**未改 `dept_id`**——删除后该字段指向已不存在的组织。
现按「向上归并」处理：

| 对象 | 处理 |
|---|---|
| 指标目标 / 指标实际值 / 任务 | 直接删除 |
| 子组织 | `parent_id` 上移到被删组织的上级（通常为 `CO`） |
| 关联账号 | 置为 `disabled`，`dept_id` 上移到上级组织（不删账号，保留历史痕迹） |

回归用例 `test_project_delete_reassigns_dangling_refs` 会校验删除后全库不存在
指向已删除组织的 `dept_id` / `parent_id`。
