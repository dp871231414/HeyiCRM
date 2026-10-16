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
⑤ 无错误：批量插入；任务名称相同的多行归组（first(parent).id 作为分组键）
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
| parent | varchar(128) | 任务名称 |
| title | varchar(128) nullable | **冗余字段**：= 主任务名称（兼容旧查询/导出，不再作为自由文本分类） |
| main_task_id | varchar(32) FK→main_task.id | 关联主任务；为空时回落到系统默认「空」(MT_NONE) |
| description | text | 任务描述 |
| abnormal | bool | 人工异常标记，默认 false |
| target | numeric(18,2) | 目标，非量化填 1 |
| done | numeric(18,2) | 已完成，非量化未完成 0 / 完成 1 |
| unit | varchar(16) | 数量单位，仅展示 |
| note | text | 进展描述 · **最新一条进展记录的冗余快照**（列表列/导出用；编辑不可直改，见 task_progress） |
| start_date / end_date | date | 计划起止 |
| dept_id | varchar(16) FK | 责任部门 |
| owner | varchar(32) | 责任人姓名 |
| created_by / created_at / updated_at | | 审计 |

### 5.4a `task_progress` 任务进展记录（round 18 新增）

进展描述从单字段升级为时间轴记录表：每次「新增进展」插入一条，历史全部保留、倒序分页展示。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK 自增 | 记录 ID（自增序即时间序） |
| task_id | varchar(32) FK→task.id | 所属任务；任务删除时级联删除 |
| content | text | 本次进展内容（必填） |
| created_by | varchar(16) FK→user.id nullable | 记录人 |
| created_at | datetime | 记录时间（时间轴展示用） |

**关键规则**
- **新建任务**：进展描述必填，写入第一条进展记录，同时冗余到 `task.note`。
- **编辑任务**：不可直接修改进展描述；只能点「新增进展」追加记录，`task.note` 随最新一条刷新。
- **列表「进展描述」列**：展示最新一条记录内容（`_enrich` 批量取每任务最大 id 的记录）。
- **接口**：`GET /tasks/{id}/progress`（倒序分页，默认 5 条，权限 `task.view` 或 `task.detail`）；`POST /tasks/{id}/progress`（追加，权限 `task.edit`）。
- **数据迁移**：升级旧库时，已有任务的 `note` 非空且无记录 → 自动转为第一条进展记录（幂等）。

### 5.5a `main_task` 主任务（独立字典表，round 15 新增）

任务分类从自由文本升级为后台独立存储的「主任务」字典。前端下拉选择、支持新增；每个主任务有不可变 ID 与可改名名称。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(32) PK | 主任务ID，格式 `MT` + 4 位序号（MT0001…）；**创建后不可变** |
| name | varchar(128) unique | 主任务名称（即选项名），可修改 |
| created_by | varchar(16) FK→user.id | 创建人 |
| created_at | datetime | 创建时间 |
| owner_id | varchar(16) FK→user.id nullable | **责任人**（round 16 新增）：主任务首次被任务选用时由该任务的责任人回填；人工维护后不再被覆盖 |
| dept_id | varchar(16) FK→organization.id nullable | **责任部门**（round 16 新增）：同上，由首个关联任务的责任部门回填 |
| updated_at | datetime | 更新时间（改名、回填均会刷新） |
| is_system | bool | 是否系统内置。系统内置项 `MT_NONE`（名称「空」）由 seed 默认创建，表示「未选择主任务」 |

**关键规则**
- 创建任务时不传 `main_task_id` → 默认关联 `MT_NONE`（名称「空」）。
- 主任务改名只改 `name`，`id` 不变；历史任务通过外键保留关联。
- 批量导入时「任务分类」列按名称匹配；不存在则自动新建主任务（记录创建人/时间）。
- 重名新增 → 409；改名时排除自身查重。
- **责任人与责任部门回填（round 16 新增）**：主任务创建时 `owner_id`/`dept_id` 为空；当某任务（非「空」主任务）首次选用该主任务并保存时，若主任务这两项仍为空，则取该任务的责任人（owner→user.id）、责任部门（dept_id）回填；已有值则保留，不覆盖人工维护结果。系统默认「空」(MT_NONE) 不参与回填。
- **下拉展示（round 18 修正）**：主任务下拉每项展示「**名称 责任人**」（如「注册新公司 胡国海」）—— 责任人为回填字段；创建人仅存数据表、不在前端体现。`+ 新增` 按钮常显在下拉选择框右侧。拥有 `task.edit` 权限者在选项后可见铅笔按钮，点击就地改名（ID 不变）；展示范围仅按角色权限（`task.view` 可见全部，`task.edit` 可改名），不做按部门的数据范围过滤。
- **存量数据回填（round 18）**：升级旧库时，责任人为空的非系统主任务取其下最早创建任务的责任人/部门回补（与「首次选用回填」同一语义）。

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
| 任务管理 | task.view | task.detail / task.edit / task.delete / task.import |
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
| POST | `/users` | 新增账号（初始密码、`scope` 必填） |
| PATCH | `/users/{id}` | 编辑；`scope` 必须显式传入四档之一 |
| POST | `/users/{id}/status` | `{status:"active"\|"disabled"}` 启停用 |
| GET | `/users/import/template` | 下载账号批量导入模板（含「部门清单」「角色清单」两个 sheet 与四个下拉校验） |
| POST | `/users/import` | 批量导入；**任一行出错则整批不写入**，回执 `{imported, errors:[{row, field, msg}]}` |
| GET | `/users/{id}/impact` | 删除前预检，返回六类引用计数（见 §9.3） |
| DELETE | `/users/{id}` | 有引用 → 409 并列出原因；禁止删自己与最后一个管理员 |

**数据可见范围（scope）必选**：自本轮起取消「跟随角色默认」语义。账号的可见范围
必须由创建人明确从 `self / dept / dept_sub / all` 四档中选定，后端 `_require_scope()`
对空值与非法值一律返回 422。这样每个账号的可见边界都是显式决策，便于事后审计，
也避免角色范围调整时账号行为随之静默漂移。

**批量导入字段约定**：必填为姓名、账号、初始密码、所属部门、角色、数据可见范围；
「状态」选填，留空默认启用。部门与角色按名称匹配（模板附清单 sheet），
可见范围支持中文标签与英文 key 两种写法。

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
| GET | `/tasks/{id}` | 详情（task.view 或 task.detail） |
| POST | `/tasks` | 新建（自动生成任务ID）；`main_task_id` 选填，不传默认 `MT_NONE`；`note` 必填（写入第一条进展记录） |
| PATCH | `/tasks/{id}` | 编辑（可改 `main_task_id`；`note` 字段被忽略 —— 进展只能追加） |
| DELETE | `/tasks/{id}` | 删除（需 task.delete 权限；级联删除进展记录） |
| GET | `/tasks/{id}/progress?page=&size=` | 进展记录倒序分页（默认 5 条；task.view 或 task.detail） |
| POST | `/tasks/{id}/progress` | 追加进展记录 `{content}`（需 task.edit；task.note 同步刷新） |
| GET | `/tasks/dept-stats?period=` | 部门任务完成度聚合（SQL GROUP BY） |
| GET | `/tasks/import/template` | 下载任务导入模板（「任务分类」列对应主任务，不存在自动新建） |
| POST | `/tasks/import` | multipart，返回 `{imported, errors[]}` |
| GET | `/tasks/export` | 导出当前可见任务 xlsx |

**列表/分组视图**：前端在「平铺列表」与「按部门分组」两种视图间切换。分组视图排序规则（round 18 修正）——部门内按主任务 **ID 归类**升序（**同一主任务跨人员排在一起**，无主任务的 `MT_NONE` 排最后），同主任务内按创建时间倒序。round 16 的「人员 ID 排序」层级已移除：主任务优先于人员，保证同一主任务下的任务相邻（如 T20260016 与 T202601 同属「华东大区营收达成」必须相邻）。

### 6.5a 主任务字典（round 15 新增）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/main-tasks` | 列表（系统「空」置顶，其余按名称排序），供前端下拉；返回 owner_id/owner_name/dept_id/dept_name/updated_at |
| POST | `/main-tasks` | 新增 `{name}` → 生成 `MT` 序号 ID，记录 created_by；重名 409 |
| PATCH | `/main-tasks/{id}` | 改名 `{name}`（ID 不变，排除自身查重） |

### 6.5b 项目管理（市场项目/商机）

市场项目与「项目公司」（`/projects`，独立核算组织）是两个概念：本模块是销售线索/商机，按阶段推进，是驾驶舱「市场项目概览」漏斗的数据来源。

**权限口径**：与任务模块一致 —— 菜单权限 `market.view` / 操作权限 `market.edit`（新建/编辑）/ `market.delete`；数据按**可见范围（scope）**隔离，归属维度为**创建人所属部门**（项目无部门字段），本人创建的项目始终可见。阶段取值固定为 10 / 25 / 50 / 75 / 90 / 100（项目导入 / 市场尽调 / 初审通过 / 联合评审通过 / 签约落地 / 交车投运）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/market-projects?keyword=&stage=&page=&size=` | 列表（服务端按可见范围过滤；stage 为空必须不传，空串 422） |
| GET | `/market-projects/{id}` | 详情（范围外 403） |
| POST | `/market-projects` | 新建（ID 自动生成 MP0001+；创建人/时间戳系统记录） |
| PATCH | `/market-projects/{id}` | 编辑（范围外 403） |
| DELETE | `/market-projects/{id}` | 删除（需 market.delete，范围外 403） |

### 6.6 驾驶舱

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/dashboard/summary?period=&org_id=` | `{headline, tone, weighted, timeProgress, vsTime, counts, wins[], risks[], points[]}` |
| GET | `/dashboard/overview?period=&org_id=` | `{annual[], project[], monitor[], projectCompare[]}` |
| GET | `/dashboard/dept-task-stats?period=&filter=` | 部门任务完成度，支持口径筛选（独立于 overview 取数） |
| GET | `/dashboard/project-funnel` | 市场项目概览：六层漏斗（项目数/牵引车/挂车，各阶段当前数量口径）+ 加权销量预测 |
| GET | `/dashboard/funnel-config` | 各阶段转化概率（默认 = 阶段百分比） |
| PUT | `/dashboard/funnel-config` | 整份保存六层概率（需 dashboard.config；全系统共用，立即影响预测） |
| GET | `/dashboard/metrics/{id}/trend?org_id=` | 该指标历史各期实际值（用于下钻趋势） |

`dept-task-stats` 的 `filter` 口径：`all` 全部（默认）/ `year` 本年新增 / `month` 当月新增 / `open` 未结束（done < target，含进行中与逾期）。年与月均取 `period`（页面顶部统计周期）所在年月，未识别取值按「全部」处理；年/月口径筛选的是**创建时间**落在所选时间范围内的任务。

`project-funnel` 口径：**漏斗为当前阶段口径** —— 每层只统计 `stage` 恰好等于该层的项目数 / 牵引车需求 / 挂车需求（不保证单调收窄，哪层项目多哪层数值大）；**销量预测按项目各自阶段的转化概率加权**：预测销量 = Σ（项目需求数 × 所在阶段概率），取整到辆。前端呈现为**条形图式漏斗**：左侧六条矩形条（宽度 = 当前阶段数值占最大层比例，浅蓝→深蓝、末层绿色），右侧逐层排列「阶段标题 + 当前数量 + 占总量百分比」，漏斗与标题文字分离；整体卡片高度压缩（每层 34px / 层间距 6px）。漏斗与预测只按角色权限开放（dashboard.view），不做数据范围裁剪，与驾驶舱其他模块同一口径。

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

### 9.3 账号删除的引用检查

账号不再允许无条件删除。只有当该账号**既不是任何数据的创建人、也没有被任何填写项选中**
时才允许删除，其余一律拒绝并返回 409 + 具体原因：

| 引用类型 | 计数来源 | 拒绝文案 |
|---|---|---|
| 任务创建人 | `task.created_by` | 创建了 N 条任务 |
| 项目创建人 | `market_project.created_by` | 创建了 N 个项目 |
| 指标创建人 | `metric_actual.created_by` | 创建了 N 条指标数据 |
| 任务责任人 | `task.owner` = 姓名 | 被 N 条任务选为责任人 |
| 项目负责人 | `market_project.owner` = 姓名 | 被 N 个项目选为负责人 |
| 部门负责人 | `organization.head` = 姓名 | 担任 N 个部门的负责人 |

另外两条兜底规则：不能删除当前登录账号自己；不能删除系统里的最后一个管理员账号。
删除前会把 `operation_log.user_id` 置空（而不是级联删日志），保证审计轨迹不随账号一起消失。

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

### 13.5 2026-10-12 · 分页、滚动表现与加载性能

#### 统计周期「本月」（M-18）

`components/MonthPicker.vue` 面板页脚改为一行：左侧「本月」快捷项，右侧可选范围提示。
点击后直接选中本机当前月并关闭面板；当前月不在 `[MONTH_MIN, MONTH_MAX]` 内时该项为禁用态。

#### 任务列表分页（T-11）

| 视图 | 取数方式 | 每页条数 | 分页位置 |
|---|---|---|---|
| 平铺列表 | 后端分页（`page` / `size`） | 50 | 表格下方，仅当超过一页时显示 |
| 按部门分组 | 一次取全量（`size=2000` 上限）后前端按部门切片 | 每组 20 | 每个部门末尾各带一个分页器 |

- 新增 `components/PaginationBar.vue`：上一页 / 第 x / y 页 / 下一页（含总数），平铺与分组共用。
- 分组视图用 `groupPages`（`Record<deptId, page>`）保存各组当前页；切换视图或改动查询条件时重置。
- 分组视图最多加载 2000 条，超出时页面给出提示，避免"看起来少了数据"的困惑。
- **注意**：同一路由下再次点击侧边栏不会重新挂载组件，因此视图模式会被保留 —— 切换视图必须走
  `switchView()` 显式重载（两种模式的取数方式不同）。

#### 冻结列与分组标题的滚动表现（T-12）

**根因**：`.col-id` 的 `w-[96px]` 只是建议值，表格自动布局把它压到实际 **87.6px**，
而 `.col-name` 的 sticky 偏移量固定按 `96px` 计算 —— 中间 8.4px 没有背景，滚动时透出下层内容。

```css
.col-id { left: 0; min-width: 96px; }   /* 锁定最小宽度，与实际偏移量对齐 */
.col-name { left: 96px; }
```

同时收窄了背景设置的范围：原先 `.table-freeze th, td { background: #fff }` 优先级过高，
把**所有行级底色都压掉了**（分组标题的 `bg-slate-100/70` 实际渲染为纯白）。
现改为只给冻结列设不透明背景，并让 hover / 分组底色在 `tr` 上生效、冻结列随之同步。

分组标题的固定：标题单元格内包一层 `.group-title`（`position: sticky; left: 12px`），
横向滚动时文字与统计数字停在容器左侧，行背景仍铺满整行。

#### 加载性能（P-1）

| 项 | 改前 | 改后 |
|---|---|---|
| 主包 JS | 169.73 KB 原样传输 | gzip **65.20 KB**（−61.6%） |
| CSS | 32.4 KB | gzip **6.5 KB** |
| 指标看板 JSON | 13.6 KB | gzip **2.2 KB**（−83.5%） |
| 构建产物缓存 | 无 `Cache-Control` | `public, max-age=31536000, immutable` |
| index.html | 无 | `no-cache`（及时拿到新版本） |
| 任务列表查询 | 全量查出后在内存切片 | SQL `LIMIT/OFFSET`，只读当前页 |

实现要点：

- `main.py` 增加 `GZipMiddleware(minimum_size=1024)`；注意中间件顺序（后添加的在更外层）。
- 静态资源用 `StaticFiles` 子类统一补 `Cache-Control`；产物名含内容哈希，可安全长期缓存。
- 任务列表的 **状态过滤下推 SQL**（`_status_condition`），与 `services.achievement.task_health`
  保持同一套语义；否则会出现「分页在 SQL 层、过滤在 Python 层」，页数与总数对不上。
  回归用例 `test_task_status_filter_matches_computed_status` 会逐个状态比对两侧结果。
- `size` 设上限 2000（`Query(ge=1, le=2000)`），避免一次拉取过多数据。

### 13.6 2026-10-12 · 数据维护工具与种子语义收敛

#### 维护工具 `app/maintenance.py`

删除账号、清空任务属于**不可逆**动作，不需要在日常界面上常驻暴露，因此做成命令行工具而非 HTTP 接口：

```bash
# 预演（只打印将删除的内容）
.venv/bin/python -m app.maintenance purge --keep admin,huguohai --dry-run
# 执行
.venv/bin/python -m app.maintenance purge --keep admin,huguohai
```

**安全护栏**（都会在违反时直接拒绝执行）：

| 护栏 | 原因 |
|---|---|
| `--keep` 不能为空 | 否则会删光全部账号，没人能登录 |
| 保留账号中须至少有一个具备 `account.role` 的账号 | 否则清理后无人能管理角色与权限 |
| `--keep` 中不存在的账号会明确提示 | 避免"以为保留了、其实被删掉" |
| `--dry-run` 支持先看清单 | 执行前确认范围 |

**关联引用的处理**：`operation_log.user_id`、`metric_actual.created_by`、`task.created_by` 都指向账号。
删除账号前先**把这些引用置空**——保留操作日志与指标数据本身，只解除指向已删账号的引用，
不留下悬空值。清理动作本身也会写一条 `purge` 日志便于日后追溯。

另有 `rename` 子命令（一次性运维动作，用于改登录账号名）：

```bash
# 改账号名（可选同时重置密码）；--dry-run 先看将发生什么
.venv/bin/python -m app.maintenance rename --account 旧名 --to 新名 --password 新密码 --dry-run
```

**为什么做成命令而不是接口**：账号名是登录标识符，界面上刻意不提供修改入口
（`UserUpdate` 里没有 `account` 字段）。改名属一次性动作，不需要常驻入口。

**引用安全性**：`operation_log.user_id`、`metric_actual.created_by`、`task.created_by`
存的都是 **user.id**（不是账号名），所以改名不会产生悬空引用 ——
这也是它比 purge 轻的原因（后者删账号前必须先把这些引用置空）。

**护栏**：目标账号必须存在；新账号名 2-32 位（字母/数字/下划线/点/连字符）；
新名已被占用则拒绝（避免顶掉他人账号）；新密码 6-128 位（与接口约束一致）。

线上执行方式与 purge 相同 —— 通过 `start.sh` 的一次性开关，复用脚本里已解析的 `DATABASE_URL`：

```bash
RENAME_FROM="旧名" RENAME_TO="新名" RENAME_PASSWORD="新密码" sh start.sh
```

### 13.7 2026-10-15 · 市场部锁定 + 漏斗按二级部门筛选 + 负责人限定与项目重生成

本轮四项改动（用户原需求 1–4）：

#### 市场部按 ID 锁定不可删除（D-40）

- 后端常量 `DEFAULT_MARKET_DEPT_ID = "D01"`；`orgs.delete_org` 在删除前判断
  `org.id == DEFAULT_MARKET_DEPT_ID` → 返回 `409「市场部为系统默认部门，不可删除，仅可修改名称与负责人」`。
- 名称与负责人仍可改（编辑接口不受影响）；二级部门（D12 / D13）**不**锁定，可自由增删。
- 前端「组织结构」列表：D01 行展示 `默认市场部 · 不可删除` 标签，删除按钮替换为 `🔒 锁定`；
  编辑按钮对 D01 仍可用。

#### 经营驾驶舱「市场项目概览」按二级部门筛选（D-41）

- 漏斗接口 `build_funnel(db, dept_id=None)` 新增 `dept_id` 过滤：传入具体二级部门 ID 时，
  只统计负责人直接归属该部门的项目；`None` 时统计市场部子树（D01/D12/D13）全体人员。
- 返回体新增 `deptOptions`：取自 `market_sub_departments(db)`（D01 直接子部门，随组织变化同步）。
- 口径：**各阶段「当前数量」统计**（`stage == 该层`，不向上累计）。漏斗口径与责任人姓名→部门映射
  （`_owner_dept_map`，仅纳入市场子树内启用账号）解耦，避免旧项目 owner 指向不存在的人污染统计。
- 前端：市场项目概览区新增筛选标签 `全部 / 市场1部 / 市场2部…`，点击即按 `dept` 重新拉漏斗。

#### 项目管理负责人限定 + 所属部门自动带出（D-42）

- 新增 `GET /meta/market-owners`：返回市场部子树内启用账号 `[{id, name, deptId, deptName}]`，供下拉与范围校验。
- `MarketProject` 新增 `owner_dept_id` 列（FK→organization，`SET NULL`）；`main.py` 启动期对旧库做
  `PRAGMA ALTER` 兼容（无该列时补列），避免旧库查询报 `no such column`。
- 前端：负责人下拉仅含市场部及下属人员（`胡启迪（市场1部）` 等形式，非市场部人员如赵国强不出现）；
  选负责人后 `onOwnerChange` 自动带出直接部门（三级部门带三级、二级带二级）写入 `owner_dept_id`；
  列表新增「所属部门」列展示 `ownerDeptName`。

#### 项目数据按市场部人员清单重新生成（D-43）

- 新增 `POST /market-projects/reseed`（需 `market.edit`）：先 `DELETE` 全部市场项目（清掉脏数据），
  再按市场子树启用人员（按 `dept_id, id` 排序）每人生成 1 个项目，确定性规则：
  阶段 `MARKET_STAGE_VALUES[idx % 6]`、牵引车 `20 + (idx*53)%200`、挂车 `牵引车×3//5`、
  负责人=该人员、`owner_dept_id=该人员部门`。ID 沿用 `MP` 号段（从 MP0001 起）。
- **关键修复**：会话 `autoflush=False`，delete 已立即执行但 `db.add` 不自动 flush，
  导致 `next_project_id` 每次都读到已清空的表、重复生成 `MP0001` 主键冲突。
  修复：清空后 `db.flush()`、循环内每轮 `db.add` 后 `db.flush()`。
- 前端「项目管理」工具条新增「重新生成」按钮 + 确认弹窗，调用该接口；造数逻辑线上线下一致。

> 线上线下对齐：本地 `dev.db` 与线上 `app.db` 的市场部人员清单以「ID + 名称」对齐
>（D01 林雪/郑凯、D12 胡启迪/冯成志、D13 周春泉），本地 5 人、线上 3 人（D01 下无直属人员），
> 处理逻辑与最终数据口径一致，仅人头数因环境既有数据不同而有差异。

#### 种子数据的语义收敛（重要）

原先各段演示数据是**独立判断**"该表是否为空"来决定是否灌入，导致一个副作用：
**管理员清空任务后，服务重启会把 14 条任务重新灌回来**，等于清理没生效。

现改为：以「库中是否连一个账号都没有」作为**首次初始化**的判据，
演示数据（账号 / 任务）只在这一刻灌入：

```python
first_init = not db.scalar(select(User).limit(1))   # 必须在灌账号之前取值
if first_init:
    ...账号...
if first_init and not db.scalar(select(Task).limit(1)):
    ...任务...
```

- 全新库：一次性灌入全部演示数据（行为不变）
- 已有库：不再因为"某张表空了"而回填 —— **删掉的数据不会复活**
- 内置角色权限对齐（`roles_synced`）保持独立，仍按升级逻辑每次执行

> 需要回到完整演示数据时，用 §13.3 的 `SEED_RESET=1 sh start.sh` 显式重置。

### 13.7 2026-10-12 · 首次加载性能诊断与优化

#### 诊断方法

`tools/diag-load.mjs`：用全新浏览器上下文（无缓存）跑一遍「打开页面 → 登录 → 进入驾驶舱」，
采集 navigation 指标、每个请求的**发起时刻**与 TTFB，从而看出链路里哪些环节在**串行等待**。

#### 诊断结论

| 项 | 优化前 |
|---|---|
| 导航 TTFB | 410 ms |
| FCP（首次内容绘制） | 1272 ms |
| 登录完成 | 2472 ms |
| 驾驶舱内容出现 | 3750 ms |

关键观察：

1. **每个请求 TTFB 都在 300–600 ms**，即使 `/api/health` 这种极简接口也一样
   —— 说明其中约 300 ms 是到托管环境的**网络往返基线**，不是服务端算得慢
   （同样接口本地实测 5 ms）。
2. **请求数不多（15 个），但串行轮次多**，每轮都要等一次往返：
   文档 → CSS/JS → 登录页 chunk → 登录接口 → 主界面 6 个 chunk → 4 个 API。
   在这种网络条件下，**减少串行轮次比压小体积更有效**。

#### 优化措施

| 措施 | 文件 | 说明 |
|---|---|---|
| 登录页改为静态导入 | `router/index.ts` | 未登录必然停在登录页，属首屏必经路径；懒加载会让首屏多一轮「主包 → 登录页 chunk」往返。代价为主包 gzip +1.8 KB |
| 登录页挂载时预取主界面 | `views/LoginView.vue` | 用户输入账号密码期间把 `AppLayout` 与 `DashboardView` 取回来，登录成功后无需再等 |
| 周期与项目公司并发请求 | `layouts/AppLayout.vue` | 两者互不依赖，原先串行 `await` 等于白等一次往返 |

#### 优化结果

单次对照（网络条件相近时）：FCP 1272 → 924 ms，登录完成 2472 → 1660 ms，
驾驶舱内容出现 3750 → 2450 ms。

多次采样（网络 TTFB 在 294–823 ms 间波动，故用区间表述）：

| 指标 | 优化前 | 优化后（3 次采样） |
|---|---|---|
| 登录完成 | 2472 ms | 1681 / 2191 / 2225 ms |
| 驾驶舱内容出现 | 3750 ms | **2609 / 3129 / 3214 ms** |

更本质的对比是**串行轮次**（与网络状况无关的结构性指标）：

| | 优化前 | 优化后 |
|---|---|---|
| 串行轮次 | 7–8 轮：文档 → CSS/JS → 登录页 chunk → 登录接口 → 6 个 chunk → 上下文（2 轮） → 业务数据 | **5 轮**：文档 → CSS/JS(+登录页) → 登录接口（与 chunk 预取并行） → 上下文（两接口并行） → 业务数据 |

按每次往返约 400 ms 计，减少 2–3 轮即省下约 800–1200 ms —— 与实测吻合。

#### 未采纳的优化及原因

- **登录接口中的 bcrypt 校验（约 250 ms）**：`bcrypt.gensalt()` 默认 cost=12。
  但 cost 是记录在**已有密码哈希里**的，调低配置只对新设置的密码生效，
  要让现有账号变快必须重置密码；且这属于安全成本，不值得为速度削弱。
- **让业务数据请求不等组织上下文**：理论上可再省一次往返，但只有「全公司可见范围」
  的用户能安全提前（其他范围的 `orgId` 需等接口返回），收益与出错风险不匹配，暂不做。

> 托管环境的网络往返是固有成本（约 300 ms/次）。已把客户端可控的串行轮次压到最少：
> 文档 → 资源 → 登录（与主界面代码并行）→ 上下文（两个接口并行）→ 业务数据。

### 13.8 2026-10-12 · 编辑权限分块与指标维护页加载

#### 编辑权限按页面三块分组（M-19）

**改前的模型**（界面上看不出对应关系）：

| 权限 | 实际作用 |
|---|---|
| `metric.edit` | **所有**指标编辑的前置条件（隐含） |
| `metric.edit_company` | 公司整体目标 **与监控指标** |
| `metric.edit_project` | 项目公司指标 |

两个问题：① `metric.edit` 是隐藏前置，勾了「维护公司整体目标」也不能编辑；
② 一个 `metric.edit_company` 同时管两块，看不出「指标监控」由谁负责。

**改后：三块各自独立，与页面一一对应**

| 页面上的一块 | 权限 | 说明 |
|---|---|---|
| 一、公司整体目标 | `metric.edit_company` | 编辑 annual 指标（公司视角） |
| 二、指标监控 | `metric.edit`（label 改为「维护监控指标」） | 编辑 monitor 指标 |
| 三、项目公司指标 | `metric.edit_project` + `project.create/edit/delete` | 编辑项目公司指标与项目公司本身 |

- **复用 `metric.edit` 这个 key 而不是新增权限点**：零迁移成本，现有角色的配置继续有效；
  只是把它的语义从「笼统的录入权」收敛为「指标监控」这一块。
- 权限目录新增可选的 `group` 字段，前端按它分块渲染（`AccountsView.actionSections`）。
- 后端 `required_metric_perm()` 按「这条指标属于哪一块 + 属于什么组织」决定所需权限，
  由 `_validate_write` 统一校验；拒绝时提示缺的是哪个权限（`PERM_LABELS` 映射中文名）。
- 判定不再要求 `metric.edit` 作为前置：
  `canEditAll = metric.edit_company ∧ 视角为公司`、`canEditMonitor = metric.edit`、
  `editableProjects = 可见范围内的项目公司（需 metric.edit_project）`。

> **行为变化**：`dept_head` 与 `member` 原本就有 `metric.edit`，改后「可编辑监控指标」。
> 但监控指标挂在公司层级，而这两个角色的可见范围不含公司 → 实际仍无法编辑，无实质影响。
> 如需收紧，在角色配置里取消勾选「维护监控指标」即可。

#### 指标维护页加载优化（M-20）

**根因**：`loadPrev()` 为**每个监控指标**各发一个 `trend` 请求（共 10 个），
且被 `await` 在 `load()` 里 —— 表格必须等全部返回才渲染。
实测 10 个并发互相争抢，尾请求 TTFB 从 299ms 递增到 **2427ms**：

| 指标 | TTFB |
|---|---|
| INC_AMT / RD_AMT | ~300 ms |
| INC_DOING | 871 ms |
| FAU_AMT | 1626 ms |
| FAU_TOT | 2427 ms |

**改动**：

1. 新增批量接口 `GET /dashboard/metrics/trends?ids=A,B,C&org_id=CO`，
   一次查询取回多个指标的趋势（`series` 保持调用方给定顺序，不存在的指标跳过）。
2. 前端改用该接口；并把 `await loadPrev()` 改为 `void loadPrev(seq)`
   —— 表格先渲染，上期值回来后再填入，同时用 `loadSeq` 丢弃过期响应。

**效果**：趋势请求 **10 个 → 1 个**；从点击菜单到表格出现 **928 / 982 / 1121 ms**
（本地 257ms）。回归用例 `test_trends_batch_matches_single` 逐个字段比对
批量与单个接口的输出，确保合并没有改变结果。

### 13.9 2026-10-12 · 组织结构的保存体验与「全公司」可编辑

#### 现象与根因

在「账号管理 → 组织结构」编辑部门，保存后列表会被清空并显示「加载中」。

根因在 `saveOrg()`：保存成功后调用 `loadOrgs()`，而 `loadOrgs()` 第一件事就是
`orgLoading.value = true`，模板里 `v-if="orgLoading"` 会把整个 `<ul>` 换成加载占位：

```html
<div v-if="orgLoading">加载中…</div>
<ul v-else>…组织列表…</ul>
```

于是每次保存都会「列表消失 → 重新出现」一次，观感等同整页刷新。

#### 改动

| 位置 | 改动 |
|---|---|
| `accounts/orgs.py` | 新增 `_org_payload()`，创建 / 更新接口返回**真实的 depth 与统计数** |
| `AccountsView.loadOrgs(silent)` | 支持静默模式：不切换加载态 |
| `AccountsView.saveOrg()` | 编辑后就地更新（`upsertOrg`），新建后静默重载 |
| `AccountsView.upsertOrg()` | 替换本地节点，并同步账号列表里显示的部门名 |
| `AccountsView` 模板 | 「全公司」也显示编辑按钮（删除仍不允许） |
| `orgs.py::update_org` | 去掉「仅可编辑部门」的限制，允许编辑公司节点 |

**为什么编辑用就地更新、新建/删除用静默重载**：
编辑只影响单个节点的名称与负责人，本地替换即可（零请求、零闪烁）；
而新建与删除会改变节点在树中的位置（扁平列表按深度优先排列），静默重载更稳妥
—— 它仍会替换列表内容，但不显示加载态，视觉上不会「闪一下」。

**顺带修掉的一个隐患**：`update_org` 原先返回 `depth: 0, userCount: 0, childCount: 0, taskCount: 0`
这样的占位值（`create_org` 也把 depth 硬编码为 1）。一旦前端改成就地更新，
这些假值会立刻体现在界面上 —— 缩进层级错乱、统计数字归零。
所以先补上 `_org_payload()`（复用 `org_counts()`），让接口返回真实数据。

#### 关于「全公司」名称的联动

顶栏「组织视角」下拉里的「全公司」是**范围标签**（表示不限定到某个项目公司），
不随根节点的名称变化；组织树里改的是组织本身的名称。
如需两者联动，需要额外取一次组织数据或调整接口，暂未做。

### 13.10 2026-10-12 · 移除「组织视角」切换

#### 业务依据

业务方明确：**全公司与项目公司不是递归汇总关系** ——
项目公司承载的是运营收入，而销售收入由系统中尚未体现的主体产生。
在这种口径下，"切到某个项目公司看"会让人误读成「全公司 = 各项目公司之和」，
因此不提供该切换。

#### 改动的边界（重要）

去掉的是**用户可切换视角的能力**，不是数据隔离：

| 概念 | 是否保留 | 说明 |
|---|---|---|
| 组织视角切换（顶栏下拉） | **移除** | 用户不能再选看哪个组织 |
| 数据可见范围（scope） | **保留** | 全公司 / 本部门 / 本部门及下属 / 本人，仍由账号决定能看到什么 |
| 项目公司的逐行维护 | **保留** | 指标维护页按行并列展示各项目公司，那是维护入口而非视角 |

`view.orgId` 的语义从「当前视角」收敛为「**当前数据范围**」：

```ts
if (auth.scope === 'all') {
  view.orgId = 'CO'                 // 全公司范围
} else if (auth.scope === 'dept' || auth.scope === 'dept_sub') {
  view.orgId = auth.user!.deptId    // 部门范围
} else {
  view.orgId = ''                   // 本人范围：不含组织维度，页面给「范围说明」
}
```

#### 连带清理

- `view.orgOptions` 整个移除（原本只服务于那个下拉）。
- **顺带省掉一次请求**：原先为了构建下拉选项，会额外拉一次项目公司列表
  （`projectApi.list()`）；现在这一步不需要了，`loadContext` 只剩 `metricApi.periods()`。
- 页面文案去掉已不可行的指引：
  - 指标维护页的范围说明条由「当前组织视角为「D01」」改为「当前数据范围为你所属的部门」；
  - 驾驶舱的「公司整体经营指标请切换组织视角查看」改为「…需要相应的数据权限」。
- 验收脚本同步：`e2e-flow.mjs`、`verify-changes.mjs`、`verify-round3.mjs` 中
  依赖 `header select` 的断言全部改写，并新增「顶栏不再提供组织视角切换」的断言
  （防止将来又被加回来）。

> 附带修好：`e2e-flow.mjs` 里还有更早遗留的失效断言（统计周期改为面板式组件后，
> 它仍在读 `header select`）。已一并改为读取月份组件的触发器文本。

### 13.11 2026-10-12 · 数据权限边界：仅任务模块按可见范围隔离

#### 结论（口径）

| 模块 | 判断依据 | 取数口径 |
|---|---|---|
| **任务管理** | 角色权限（`task.*`）+ **数据可见范围** | 按可见范围收窄（列表 / 详情 / 部门统计） |
| 经营驾驶舱 | 只按角色权限（`dashboard.view`） | 全公司口径（含其中的任务统计） |
| 指标维护 | 只按角色权限（`metric.view` / `metric.edit_*` / `project.*`） | 全公司口径（项目公司列出全部） |

依据：全公司与项目公司不是递归汇总关系（项目公司只承载运营收入，销售收入来自系统中的其他主体）。
按部门可见范围裁剪经营数据，会让部门账号看不到完整口径，反而造成误读。

#### 改动清单

| 文件 | 改动 |
|---|---|
| `api/v1/dashboard.py` | 4 个接口去掉 `org_in_scope` 校验；`build_board` 不再传可见组织；改用 `dept_stats_all(db)`（不传可见性条件） |
| `api/v1/metrics.py` | `board` 去掉范围校验；`editableProjects` 改为「有 `metric.edit_project` 即全部项目公司」；`_validate_write` 去掉 `org_in_scope`；`build_board` 移除 `visible_orgs` 参数 |
| `api/v1/projects.py` | 列表不再按可见范围裁剪；编辑 / 删除去掉范围兜底 |
| `api/v1/tasks.py` | 抽出 `dept_stats_all(db, cond=None)`：任务模块传 `visible_task_filter`，驾驶舱不传；**其余逻辑不变（仍按范围隔离）** |
| `services/summary.py` | 任务侧去掉 `visible_task_filter`；`build_summary` 去掉 `user` 参数 |
| `services/scope.py` | 模块文档改写为「只作用于任务模块」；删除已无使用者的 `org_in_scope` |
| 前端 | `AppLayout.loadContext` 中 `view.orgId` 固定 `'CO'`；移除「本人范围」空态与部门范围提示条；清理 `DashboardView` 多余的 `auth` 依赖 |

#### 影响的既有行为（有意为之）

- 部门范围账号现在能看全公司经营数据（原先 403 或按部门裁剪）；
- 项目公司负责人可维护**全部**项目公司（原先仅自家）；
- 驾驶舱里的「部门任务完成度」对所有人一致（全量口径）。

> **注意**：任务模块的隔离没有被削弱 —— 验收脚本会用同一账号对比两个模块：
> 管理员 3 条任务 → 部门负责人 1 条（任务侧仍收窄），而驾驶舱与指标维护的数据完全一致。

### 13.12 2026-10-13 · Minimalist Modern 设计系统落地

#### 落地策略：取视觉基因，换结构语言

新设计系统是**营销落地页**配方（hero、pricing、testimonials、3D 等距变形、浮动装饰卡）。
本项目是数据密集型后台。逐项取舍：

| 设计系统的元素 | 本项目如何处理 |
|---|---|
| 签名渐变（Electric Blue） | ✅ 全量采用，色阶两端点即渐变端点 |
| 彩色阴影（accent-tinted） | ✅ 全量替换原中性灰阴影 |
| 抬升式交互（hover lift） | ✅ 按钮、可交互卡片 |
| 区块标识（Section Label） | ✅ 登录页用完整 pill 徽章；数据页用**渐变短竖条**（更克制） |
| 反转对比区（Inverted Section） | ✅ 落在驾驶舱「分析总结」（全页最重要的结论） |
| 纹理层次（点阵 / 光晕） | ✅ 深色卡点阵、全局背景光晕 |
| 双字体系统（Calistoga + Inter + Mono） | ⚠️ 受「零外部字体」约束 → 用**字重/字距/等宽数字**替代 |
| 3D 等距变形、浮动装饰卡 | ❌ 数据表格会变形、且分散注意力，不采用 |
| hero 三栏网格、pricing 卡、testimonial | ❌ 营销页专属结构，后台无对应场景 |

> 字体约束是**项目的既有决定**（外链在国内超时、且属渲染阻塞），不是本次的取舍。
> 补充：Calistoga 是纯拉丁衬线体，**不含中文字形**，中文标题本来也无法用它。

#### 设计代币（`tailwind.config.js`）

```js
brand: { 400: '#4D7CFF', 600: '#0052FF', ... }   // 400/600 即设计系统的渐变两端点
boxShadow: {
  card:      '0 4px 20px -2px rgba(0, 82, 255, 0.10)',
  cardHover: '0 10px 25px -5px rgba(0, 82, 255, 0.15), 0 8px 10px -6px rgba(0, 82, 255, 0.10)',
  btn:       '0 4px 14px 0 rgba(0, 82, 255, 0.30)',
  btnHover:  '0 8px 24px rgba(0, 82, 255, 0.35)',
}
letterSpacing: { display: '-0.02em' }
fontFamily: { mono: ['ui-monospace', 'SFMono-Regular', ...] }   // 替代 JetBrains Mono
animation: { float, 'float-slow', 'spin-slow', 'pulse-dot' }
```

**为什么色阶取这两个值**：`600 = #0052FF`、`400 = #4D7CFF` 正好是设计系统签名的起止色，
于是「单色阶 + 单色渐变」自洽 —— `from-brand-600 to-brand-400` 就是官方渐变，
无需再引入第二个色相（旧方案是靛蓝 + 紫双色相）。

#### 基础组件（`styles/main.css`）

| 类 | 要点 |
|---|---|
| `.card` / `.card-lift` | 16px 圆角 + 品牌阴影；`.card-lift` 只给「点得动」的卡片（静态容器加抬升会误导） |
| `.btn` 系列 | 12px 圆角、200ms、hover 抬升 2px、按下缩到 0.98；**disabled 时显式关闭抬升与阴影** |
| `.input` | 8px 圆角，焦点 `border-brand-500 + ring-2 ring-brand-500/25` |
| `.section-title` | 特粗 + `-0.02em`，左侧 `::before` 渐变竖条（区块标识） |
| `.section-label` | pill 徽章 + 脉冲圆点，用于登录页等需要强调的场景 |
| `.stat-value` | `tabular-nums`，让数值纵向对齐 |
| `.dot-grid` | 点阵纹理，铺在深色容器上 |
| `.gradient-text` | 渐变文字（克制使用，登录页等强调位） |

无障碍：新增 `@media (prefers-reduced-motion: reduce)` 兜底，装饰动画（浮动/旋转/脉冲）全部停用。

#### 深色反转卡（驾驶舱分析总结）

| 元素 | 处理 |
|---|---|
| 容器 | `bg-slate-900` + `border-slate-800/60` + `shadow-pop` + `rounded-xl2` |
| 纹理 | 绝对定位 `.dot-grid` 覆盖层，`opacity-[0.06]` |
| 光晕 | 右上角 56×56 模糊圆，颜色随语义变化（`toneGlow`） |
| 语义标签 | 由「浅底深字」改为「半透明底 + 亮色字」：`bg-good-500/15 text-good-500 border-good-500/30` 等 |
| 正文 | `text-slate-100` / 次要 `text-slate-300` / 更弱 `text-slate-400` |
| 统计小卡 | `bg-white/10 border-white/10` |

> **为什么改语义标签配色**：原先的 `bg-good-50 text-good-700` 是给浅色背景设计的，
> 直接搬到 `slate-900` 上会糊成一片且对比度不足。深色场景必须换成「半透明色底 + 中亮色字」。

#### 旧叫法清理（M-25）

统一为「任务名称 / 任务分类 / 任务描述」一套命名（导入模板、列表、表单三处一致）。
数据字段 `parent` / `title` 与列表列保持不变。清理范围：前端 label、后端 schema 描述与注释、
README、交接说明、proposal、design、layouts。

> **有意保留**：`tests/test_changes.py` 中的一条负向断言
> （`assert "一级任务" not in TASK_COLUMNS ...`）—— 它是防止旧叫法回归的守卫，
> 字面量本身即是检查目标，不能一并替换掉。

#### 验收脚本的环境差异（本轮踩到并修正）

`verify-round7.mjs` 需要以管理员身份造数与改账号，最初的实现用 `fetch` + `Authorization: Bearer`。
本地通过、**线上全部 401**：

```
GET /users  → 401 {"detail":"未登录或登录已过期"}   （token 是刚登录拿到的，有效）
```

原因是**线上网关会注入/覆盖 `Authorization` 头**，后端收到的是网关的 token
（项目测试里 `...gateway-injected-junk...` 那条用例即为此现象）。Cookie 认证不受影响，
这正是浏览器脚本一直能在线上跑通的原因。

修正：管理端调用改用**独立的浏览器上下文**（`browser.newContext()` 的 `context.request`）：

| 方案 | 本地 | 线上 | 结论 |
|---|---|---|---|
| 页面上下文 + request | ❌ 会以页面账号发请求，清理步骤 403 | ❌ 同左 | 不可用 |
| `fetch` + Bearer | ✅ | ❌ 网关覆盖 Authorization | 不可用 |
| **独立上下文的 request（Cookie）** | ✅ | ✅ | **采用** |

同时把所有验收脚本的凭据统一改为环境变量（`DIAG_USER` / `DIAG_PWD` / `HEAD_USER` / `HEAD_PWD`），
避免线上密码变更后脚本失效。

### 13.13 2026-10-13 · 驾驶舱总结卡改浅色与指标卡配色统一

#### 分析总结卡：底色反转 → 色条 + 徽章

深色反转卡（Inverted Contrast Section）在营销落地页里成立 —— 那里的周围是留白与浅色块，
深色区能形成节奏。但在数据密集型后台，它被夹在一堆浅色卡片中间，反而割裂。

改回浅色白卡后，状态靠两处表达：

| 元素 | 作用 |
|---|---|
| 左侧 4px 语义色条（`toneAccent`） | 一眼看出整体状态（绿/黄/红，无数据为品牌蓝） |
| 状态徽章（`toneChip`） | 文字化的状态（整体良好 / 需要关注 / 存在风险 / 暂无数据），浅底深字 |

同时移除了只服务于深色底的 `.dot-grid` 纹理与模糊光晕。

#### 核心指标：一张卡一种颜色

**改前的问题**：同一张卡里三处各自取色 ——

| 元素 | 取色依据（改前） |
|---|---|
| 状态徽章 | 后端 `light`（实际 vs 目标，含 `warn`/`danger` 阈值） |
| 达成率文字 | 同上 |
| 进度条 | 同上 |
| 「vs 时间进度」 | 按正负取绿/红 |

于是会出现「徽章红、vs 时间进度绿、进度条红」这种自相矛盾的卡片
（例：完成率 82%、目标 12000、实际 9860 → 徽章红；但时间进度 78.4% → vs 时间 +3.8% 绿）。

**改后**：新增表现分级 `perfTone(row)`，三处共用：

```ts
function perfTone(row) {
  if (row.rate === null) return 'none'          // 未录入 → 灰
  if (row.rate >= 1) return 'done'              // 已完成 → 绿
  const ratio = row.rate / overview.timeProgress
  if (ratio >= 1) return 'ahead'                // 领先时间 → 蓝
  if (ratio >= 0.7) return 'near'               // 略慢 → 黄
  return 'risk'                                 // 明显滞后 → 红
}
```

| tone | 徽章文案 | 进度条 | 文字 |
|---|---|---|---|
| done | 已达成 | `bg-good-500` | `text-good-600` |
| ahead | 领先 | `bg-brand-500` | `text-brand-600` |
| near | 偏慢 | `bg-warn-500` | `text-warn-600` |
| risk | 滞后 | `bg-bad-500` | `text-bad-600` |
| none | 未录入 | `bg-slate-300` | `text-slate-400` |

**为什么「已完成」优先于比值**：完成率 ≥ 100% 时比值必然 ≥ 1（时间进度 ≤ 100%），
若不加判断会显示成蓝色「领先」，弱化了「已经达成」这个更强的事实。

**「vs 时间进度」改为中性灰**：它的正负与卡片 tone 是同源的，
再单独着色会出现「蓝卡配绿字」的错位；数字自带 +/- 号，信息不丢。

**卡内次要指标（回款率）**：它有独立目标（`rate_target`，默认 95%），
若一直着色会让卡片出现第二种色相。改为**仅未达目标时着色**（黄/红），
达标时用中性深灰 —— 卡片主色只留给表现分级。

#### 未改动的部分

- **项目公司经营对比表**里的「完成率」仍是原有阈值（≥98% 绿 / ≥90% 黄 / 否则红）：
  它是「各指标达成率的平均值」，与单指标的「完成率 ÷ 时间进度」不是同一口径，
  且属表格而非卡片，本轮不动。
- 部门任务完成度的状态标签、风险与异常的类别标签保持原样（各自语义独立）。

### 13.14 2026-10-13 · 状态口径统一（一个判定，两页共用）

#### 问题：两套判据，两种结论

| 页面 | 判据 | 运力收入（目标 26000 / 实际 21320 / 时间进度 78.4%） |
|---|---|---|
| 经营驾驶舱 | 达成率 ÷ 时间进度 | 82.0% ÷ 78.4% = 1.05 → **领先** |
| 指标维护 | 实际 vs 目标（`light_of`，含 warn 0.95 阈值） | 21320 < 26000×0.95 → **未达标** |

`light_of` 对年度目标天然不适用：**年度目标没走完时，只要没到 100% 就是红**，
年中看等于恒为「未达标」（本轮实测 6 项指标全红），信息量为零。
而驾驶舱用的是进度与时间的比值，是更有意义的口径。

#### 统一后的模型

**判定在服务端一处**：`services/achievement.progress_tone(rate, time_progress)`

| 档 | 条件 | 标签 |
|---|---|---|
| done | 达成率 ≥ 100% | 已达成 |
| ahead | 达成率 ÷ 时间进度 ≥ 1 | 领先 |
| near | 比值 0.7 ~ <1 | 偏慢 |
| risk | 比值 < 0.7 | 滞后 |
| none | 无目标值 / 未填实际值 | 未录入 |

- 「已完成」优先于比值：达成率 ≥ 100% 时比值必然 ≥ 1，不加判断会显示成「领先」，
  弱化更强的事实。
- 该判定用于：驾驶舱卡片徽章与进度条、指标维护状态列与达成率文字、
  汇总统计、分析总结的亮点/风险分组与文案、项目公司完成率。

#### 字段与命名

| 字段 | 含义 | 取值 |
|---|---|---|
| `tone` | **单指标进度状态**（本轮新增） | done / ahead / near / risk / none |
| `verdict` | **整体经营结论**（原 `summary.tone`，本轮更名） | good / warn / bad / none |
| `light` | 目标达成判定（实际 vs 目标，含 warn/danger 阈值） | green / amber / red / none |

**为什么把整体结论从 `tone` 改名为 `verdict`**：它和单指标的 `tone` 是两个东西，
只是恰好同名 —— 名字撞车正是这次混淆的温床。`light` 保留在接口里
（回款率等有独立目标的子指标仍在用它的同类 `collLight`），但**界面不再用它判定指标状态**，
`utils/format.ts` 的 `LIGHT_LABEL` 旁已加说明，避免后来者又拿它去做指标徽章。

#### 前端：样式集中一份

新增 `utils/tone.ts`（`TONE_LABEL` / `TONE_CHIP` / `TONE_TEXT` / `TONE_BAR` / `TONE_DOT` / `toneOf`），
驾驶舱与指标维护共用。原来两页各写一套标签与配色 —— 这也是「同一指标两种说法」能长期存在的土壤。

**顺带收口的两处**：

- 指标维护的「vs 时间进度」原按正负着色（与卡片主色冲突），改中性灰；
- 指标维护的「完成率」列原用硬编码阈值（≥98% 绿 / ≥90% 黄 / 否则红），
  改用后端 `completionTone`（同一套判档）；
- 回款率（有独立目标的子指标）两页统一为「仅未达目标时着色」。

#### 一处**未改动**的地方（需业务确认）

分析总结的整体结论 `verdict` 仍按绝对值判定：`加权达成率 < 0.9（或滞后 ≥ 2 项）→ 存在风险`。
本轮实测「加权达成率 83.8%、年度时间进度 78.4%」→ 判定为 `bad`，
文案却是「整体**低于时间轴**」—— 实际是**跑赢**时间进度 5.4pp，措辞与事实相反。
这与单指标的问题同源（拿年度绝对目标衡量年中进度）。
未贸然改动是因为它改变的是**经营结论**（属于业务判断），
建议后续按「加权达成率 ÷ 时间进度」对齐，是否调整待确认。

### 13.15 2026-10-13 · 分析总结结论与指标口径对齐

#### 上一批遗留的问题

§13.14 把单指标状态统一为「达成率 ÷ 时间进度」，但分析总结卡的**整体结论**仍是另一套：

```python
if weighted < 0.9 or len(lag) >= 2:   # 绝对值门槛
    verdict = "bad"
elif weighted < 0.98 or len(lag) >= 1:
    verdict = "warn"
```

后果是同一句话自相矛盾：实测「加权达成率 83.8%、年度时间进度 78.4%」被判为 `bad`，
文案输出「整体**低于时间轴**」——而它其实**跑赢**了 5.4pp。

根因与单指标那次完全相同：**拿年度绝对目标衡量年中进度**。
既然单指标已经改用比值，汇总层也不该留着绝对值。

#### 改动

整体结论直接复用同一个函数，阈值也一致：

```python
verdict = {
    "done": "good", "ahead": "good", "near": "warn", "risk": "bad", "none": "none",
}[progress_tone(weighted, tp)]
```

同时**去掉了「滞后项数」条件** —— 原先 `滞后 ≥ 2 项 → bad` 是第二套判据，
会与比值结论打架；整体结论只由加权达成率与时间进度的比值决定。

文案改为与时间进度挂钩，避免再出现与事实相反的表述：

| verdict | 徽章 | 结论文案 |
|---|---|---|
| good | 跑赢时间进度 | 整体跑赢年度时间进度，目标可控 |
| warn | 略慢于时间进度 | 整体略慢于年度时间进度，存在局部缺口需关注 |
| bad | 滞后时间进度 | 整体明显滞后于年度时间进度，存在明确风险需立即干预 |

> 档位仍是三档（good / warn / bad）：整体层面不需要区分「已完成」与「领先」，
> 所以 `done` 与 `ahead` 都归为 good —— **判据与阈值与单指标一致，只是展示粒度更粗**。

#### 实测（造数验证三档，验完已还原）

| 造数（各指标达成率） | 加权 ÷ 时间进度 | 结论 | 卡片 |
|---|---|---|---|
| ≈ 100%（原始数据） | 84.2% ÷ 78.4% = 1.07 | 跑赢时间进度 | 6 项全「领先」 |
| ≈ 60% | 60.0% ÷ 78.4% = 0.77 | 略慢于时间进度 | 6 项全「偏慢」 |
| ≈ 40% | 40.0% ÷ 78.4% = 0.51 | 滞后时间进度 | 6 项全「滞后」 |

三档中汇总结论与卡片标签的分布始终一致。

#### 验收脚本的一处修正（同类坑第二次）

`verify-round9.mjs` / `verify-round10.mjs` 原来靠**文案匹配**定位分析总结卡
（`/整体良好|需要关注|存在风险/`）。本次改了措辞后，这两个断言立刻假失败 —— 卡片其实一直在，
只是找不到。已改为**按位置定位**（`main` 里的第一个 `section`，
并用「含『综合加权达成率』」做二次确认）。

> 规律：**断言不要依赖会被改动的文案**。这类失败最浪费时间 ——
> 看起来像功能挂了，实际是选择器过期。同理，界面上任何会变的文字都不适合做定位锚点。

### 13.15 2026-10-16 · 列宽固定 + 省略号 + 行高偏好（任务 / 项目双页一致）

#### 需求（用户原话拆解）

1. **列序交换**：任务管理列表「主任务」「任务名称」两列互换，主任务在前。
2. **固定列宽 + 省略号**：所有列固定宽度；其中「任务名称 / 主任务 / 进展描述」分别按 20 / 20 / 30 个汉字长度固定（≈ 320 / 320 / 460px），超出部分用「…」截断，鼠标悬停（`title`）展示完整内容。
3. **行高设置（按账号记忆）**：筛选栏新增「行高」下拉 —— 默认 / 高（2X）/ 超高（3X）；选项按用户账号记忆，下次登录仍生效；选择后**所有行高**一次性调整，字体支持折行，仍未展示完整的部分用「…」截断。

#### 后端：用户偏好持久化

| 文件 | 改动 |
|---|---|
| `models/user.py` | `User.preferences` 新增 JSON 列（默认 `{}`，`nullable=False`） |
| `services/serializers.py` | `user_brief` 序列化带入 `preferences` |
| `schemas/auth.py` | `UserBrief.preferences`、新增 `PrefsOut` / `PrefsUpdate` |
| `api/v1/auth.py` | 新增 `GET /auth/preferences`、`PUT /auth/preferences`（白名单：`rowHeight ∈ {default,high,ultra}`，其余键/值静默忽略，浅合并写入） |
| `main.py` / `seed.py` | 老库 ALTER 补 `user.preferences` 列（TEXT，默认 `'{}'`） |

前端「行高」选择器切换时调用 `auth.updatePreferences({ rowHeight })`：乐观更新本地 → `PUT /auth/preferences` 写回 → 登录 / `/auth/me` 自动回带，下次登录载入。

#### 前端：列宽 / 省略号 / 行高

| 维度 | 实现 |
|---|---|
| 列序交换 | 任务管理表头 `任务ID → 主任务 → 任务名称 → 进展描述 → …`；主任务列冻结类 `col-maintask`（`left:96px`），任务名称 `col-name` 冻结于 `left:309px`（96+213） |
| 固定列宽（table-fixed） | 表格用 `table-fixed`（Round 20 修复：原先自动布局下长内容会把列撑开，固定与省略号都未真正生效）；三特殊列固定 `213/213/307px`（约 13/13/20 汉字，较最初 320/320/460 减 1/3）；其余列保持 `w-[]` 固定；表格总宽固定 `w-[2219px]` |
| 省略号 + 悬停 | 特殊列内容包 `.cell-c`：`title` 展示全文；默认单行 `text-overflow: ellipsis`；高/超高行高切 `-webkit-line-clamp: var(--cell-lines)` 多行折行再省略。固定 `td` 宽度下 ellipsis 才真正触发（Round 20 修复） |
| 行高 | 表格挂 `rh-{default,high,ultra}`：固定 `.td` 高度（44 / 88 / 132px ≈ 1X/2X/3X），高/超高 `vertical-align:top`；`--cell-lines` 控制截断行数（3 / 5） |

项目管理（ProjectsView）复用同一套 `.cell-c` / `rh-*` 机制：项目名称（20 汉字 / 320px）、项目描述（30 汉字 / 460px）固定列宽 + 省略号，筛选栏同样提供行高下拉。（注：本轮 Round 20 仅调整任务管理三列宽度；项目管理列宽维持 320/460 不变，待后续按需同步。）

#### 注意点

- `.cell-c` 与冻结列背景同步：高/超高行高时冻结列（`.col-id/.col-maintask/.col-name/.col-ops`）的 sticky 背景与 hover 底色规则已一并覆盖，避免「冻结列不变色」的割裂感。
- 本地验证：`STATIC_DIR` 环境变量未设置时静态不挂载（默认空），`start.sh` / 部署环境会注入正确路径；联调用 `STATIC_DIR=.../backend/static` 显式指定。
