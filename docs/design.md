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
