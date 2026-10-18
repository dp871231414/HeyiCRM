# 合一重卡生态经营看板 · 技术设计（design）

> 版本：v2.4 · 2026-10-18
> 上游：`docs/proposal.md`（需求编号 A/O/R/U/M/T/D/I/K/S/X）
> 说明：本文回答「用什么技术、模块如何协作、如何部署」。技术栈已锁定，本文严格遵守现状（SQLite 单文件库 + 单端口同源托管），并并入 Round 23 的系统配置·数据字典、项目管理车头/挂车需求子列表两项改造，以及 Round 24 的下载中心（X-1~X-6）。v2.2 调整导出口径（导出仅返回下载中心记录 JSON，不再即时下载）并移除「重新生成」入口（原 `POST /market-projects/reseed`）。**v2.3 菜单归并 + 字段全栈重命名：前端「账号管理」「下载中心」移入「系统配置」二级菜单；任务管理「主任务」全栈更名为「任务组」——模型 `MainTask`→`TaskGroup`（表 `main_task`→`task_group`）、`Task.main_task_id`→`task_group_id`、`services/importer.py` 与 `services/achievement.py` 的 `MT_NONE_ID`/`MT(\d+)`→`TG_NONE_ID`/`TG(\d+)`、API 路由 `/main-tasks`→`/task-groups`（文件 `main_tasks.py`→`task_groups.py`，router 同步）、前端 `api/index.ts` 与 `TasksView.vue` 的 `mainTask*`/`MT_NONE_ID`→`taskGroup*`/`TG_NONE_ID`；演示库经 `SEED_RESET=1`（start.sh 现已支持硬重置：删库文件后重建）重置为 `TG` 前缀 ID。**v2.4 责任人默认与范围过滤 + 任务组联合唯一与删除 + 字段长度限制 + 项目描述必填：新增 `services/scope.py:visible_user_filter(db,user)` 供责任人下拉按 `effective_scope`（账号 scope 覆盖角色 scope）过滤；`api/v1/meta.py:owner_options` 仅返回范围内已启用账号；`models/log.py:TaskGroup.name` 去掉库级 `unique`（唯一性改为「名称 + owner_id」接口层校验）；`main.py` 启动时迁移去掉旧唯一索引（SQLite 3.50 支持 `DROP CONSTRAINT`，失败兜底整表重建）；`api/v1/task_groups.py` 新增 `owner_id` 入参、`DELETE /task-groups/{id}`（有引用任务先回退 `task_group_id=TG_NONE`，`is_system` 不可删）、名称长度校验 25；`schemas/task.py` 与 `schemas/project.py` 加字段长度校验器；`services/importer.py` 任务组按「名称 + 责任人」解析与新建、导入长度/必填校验；前端 `TasksView`/`ProjectsView` 加 `maxlength` 与保存校验、`任务组`下拉加宽并支持删除。**

---

## 1. 技术选型及理由

| 层 | 选型 | 为什么选它 | 备注 |
|---|---|---|---|
| 后端语言 | Python 3.13 | 团队熟悉；数据处理与算法（达成率、加权、导入校验）表达清晰；生态成熟 | 运行环境 `/Users/gavin/.workbuddy/binaries/python/envs/fleet`（3.13.12） |
| Web 框架 | FastAPI 0.115 | 原生异步、自动生成 OpenAPI 文档、Pydantic v2 强校验降低接口脏数据 |  |
| ORM | SQLAlchemy 2.0.36（同步） | 2.0 声明式类型化、聚合可下推到 SQL | 会话 `autoflush=False`，需显式 `flush()` 处已注明 |
| 数据库 | **SQLite 单文件库**（默认 `app.db`） | 当前部署形态：单容器、单文件、零运维；并发写入量级低，足够支撑 | `DATABASE_URL` 可指向 PostgreSQL，引擎按 `is_sqlite` 分支构造 |
| 鉴权 | JWT（HttpOnly Cookie + Authorization 双通道） | 无状态，天然支持水平扩展；线上网关会改写 `Authorization`，故以「头优先、Cookie 兜底」解析 | 见 §9 |
| 密码 | bcrypt（passlib） | 加盐哈希、抗暴力破解 |  |
| Excel | openpyxl 3.1 | 读写模板、单元格校验、错误高亮均可实现 |  |
| 前端框架 | Vue 3 + TypeScript + Vite 6 | 组合式 API 便于按模块封装；TS 提供接口类型约束 | node 22.22.2-6 |
| 样式 | Tailwind CSS | 与设计令牌对齐，原子类保持一致性 |  |
| 状态 | Pinia | Vue 3 官方推荐，TS 友好 |  |
| HTTP | Axios | 拦截器统一处理令牌与错误 |  |
| 部署 | 单端口同源托管（后端 `StaticFiles` 直挂 SPA） | 前后端同一域名、同一进程，无跨域；发布即用 WorkBuddy `sites` | 见 §11 |

> **与旧版（v1.0）的差异**：v1.0 描述的 PostgreSQL 15 + Docker Compose + Nginx 反代，并非当前线上形态。代码层面仍保留接 PostgreSQL 的能力（`DATABASE_URL` 切换），但默认与发布链路均为 SQLite 单文件 + 单容器。本版以此为准。

---

## 2. 总体架构

```
                          ┌──────────────────────────────────────────┐
   浏览器  ────────────────▶│  单容器（托管沙箱）                       │
   (Vue SPA)               │   FastAPI (Uvicorn, 0.0.0.0:$PORT)       │
                          │    ├─ /            → 托管 frontend/dist    │
                          │    └─ /api/v1/*     → 业务接口             │
                          │           │                               │
                          │           ▼                               │
                          │   API 层  /api/v1/*                       │
                          │    ├─ auth / orgs / projects / roles       │
                          │    ├─ users / metrics / tasks / dashboard  │
│    ├─ market-projects / system/dicts       │
│    ├─ downloads（下载中心）                  │
│    └─ deps: JWT 鉴权 + 权限/范围依赖       │
                          │   Service 层（业务纯逻辑）                 │
                          │    ├─ achievement 达成率/红黄绿灯/回款      │
                          │    ├─ summary     规则生成分析总结          │
                          │    ├─ scope       可见范围（组织/任务/项目）│
                          │    └─ importer    Excel 解析 + 逐行校验     │
                          │   Model 层（SQLAlchemy 2.0）              │
                          │           │                               │
                          │           ▼                               │
                          │   SQLite 单文件库（app.db）               │
                          └──────────────────────────────────────────┘
```

**分层与边界**：API 层只做参数解析、鉴权、调用 Service、组装响应；Service 层为纯业务逻辑（可单测、与框架无关）；Model 层只管持久化。**聚合计算下推到 SQL**（`GROUP BY`），禁止把上千行拉到 Python 循环。

**单容器要点**：`start.sh` 导出 `STATIC_DIR=./static`，`main.py` 在挂载 `/api` 路由后，用 `StaticFiles` 把 `STATIC_DIR` 挂到 `/`，并对 SPA 深链回退到 `index.html`。前端构建产物 `frontend/dist` 在发布前同步进 `backend/static`。

---

## 3. 模块划分与职责

| 模块 | 职责 | 对外接口 | 依赖 |
|---|---|---|---|
| `core/security` | 密码哈希、JWT 签发与校验 | `hash_password` / `verify_password` / `create_token` / `decode_token` | 无 |
| `core/deps` | FastAPI 依赖：当前用户、权限校验、范围校验 | `get_current_user` / `require_perm(key)` / `require_any_perm(keys)` | security, models |
| `services/achievement` | 达成率、状态分级（progress_tone）、回款率、时间进度、加权 | `calc_achievement` / `progress_tone` / `collection_rate` | models |
| `services/scope` | 依据角色/账号范围返回可见组织、任务、市场项目 | `visible_org_ids` / `visible_task_filter` / `visible_market_project_filter` | models |
| `services/summary` | 规则生成分析总结（结论/亮点/风险/建议） | `build_summary` | achievement, scope |
| `services/importer` | Excel 模板定义、解析、逐行校验、入库 | `parse_rows` / `validate_*` / `import_*` / `build_*_template` | models |
| `api/v1/*` | 路由 | REST | 全部 service |
| `models/*` | ORM 表 | — | db |
| `seed` | 初始化组织/指标/角色/演示账号/数据字典 | CLI | models |

---

## 4. 端到端数据流

**示例：管理员维护「市场项目」车头/挂车需求（Round 23 子列表形态）**

```
① 前端 ProjectsView 编辑表单：列头表格录入多行车头需求（车辆型号/电池度数/数量）
② POST /api/v1/market-projects  body={name, stage, owner, ownerDeptId, tractorRequirements:[{model,battery,qty}], ...}
③ deps.require_perm("market.edit") 校验按钮权限
④ scope_svc.visible_market_project_filter 校验归属（按创建人部门）
⑤ _apply_payload 计算 p.tractor_demand = Σ 明细 qty；p.trailer_demand 同理（冗余汇总快照）
⑥ _reconcile_requirements 先删后插：project_tractor_requirement 整份替换为本次提交的明细行
⑦ 写 operation_log，返回 200 {tractorRequirements:[...], tractorDemand:N}
⑧ 列表「车头数量」= tractor_demand（汇总值）；点击详情/编辑才展开明细子列表
```

**示例：操作员导入任务 Excel**

```
① 前端上传文件 → POST /api/v1/tasks/import (multipart)
② importer.parse_rows 读取工作簿 → 定位表头行（兼容顶部说明栏）→ 逐行解析为 dict
③ validate_task_rows 逐行校验 → 得到 errors[]
④ 有错误：返回 {imported:0, errors:[{row,field,msg}]}，全量校验、整批不写入
⑤ 无错误：批量插入；同名任务多行归组；写 operation_log，返回 {imported:N}
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
| created_at / updated_at | datetime | | 审计字段 |

> 项目公司 `type=project`，`parent_id=CO`，不参与组织树下拉（`deptTree` 排除 project）。市场部 `D01` 为系统默认部门，锁定不可删除（仅可改名/改负责人）。

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
| warn / danger | numeric(6,4) | 黄/红灯阈值 |
| rate_target | numeric(6,4) | 回款率目标（默认 0.95） |
| is_snapshot / no_target | bool | 期末快照 / 监控无目标 |
| owner_org_id | varchar(16) FK | 责任部门 |
| description / sort_order | text / int | 口径说明 / 展示顺序 |

### 5.3 `metric_target` / `metric_actual`

| 字段 | 类型 | 约束 |
|---|---|---|
| id | bigserial PK | |
| metric_id / org_id / period | FK / FK / varchar(8) | unique(metric_id, org_id, period) |
| value | numeric(18,2) | |
| created_by / updated_at | FK user / datetime | actual 特有 |

### 5.4 `task` 重点任务

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(32) PK | T202601… |
| parent | varchar(128) | 任务名称 |
| title | varchar(128) nullable | **冗余字段** = 任务组名称（兼容旧查询/导出） |
| task_group_id | varchar(32) FK→task_group.id | 关联任务组；空时回落 `TG_NONE` |
| description / abnormal / target / done / unit / note | text/bool/numeric… | 任务描述 / 异常标记 / 目标 / 已完成 / 单位 / **最新进展冗余快照** |
| start_date / end_date | date | 计划起止 |
| dept_id | varchar(16) FK | 责任部门 |
| owner | varchar(32) | 责任人姓名 |
| created_by / created_at / updated_at / preferences | | 审计；用户级偏好（行高记忆等） |

**计算列（不落库）**：完成进度 = round(done/target×100)；剩余天数与逾期/临期判定；健康度 = 时间判定 ⊕ 人工异常。

### 5.5 `task_group` 任务组字典

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(32) PK | `MT` + 4 位序号；**创建后不可变** |
| name | varchar(128) unique | 任务组名称（可改） |
| created_by / created_at / updated_at | | 审计 |
| owner_id / dept_id | FK user / FK org | 责任人/部门（首次被任务选用时回填，人工维护后不覆盖） |
| is_system | bool | 系统内置 `TG_NONE`（名称「空」） |

### 5.6 `user` / `role`

`role`：id / name(unique) / description / scope(self|dept|dept_sub|all) / is_system / permissions(json)。
`user`：id / name / account(unique) / password_hash / dept_id / role_id / scope(nullable) / status(active|disabled) / preferences(json) / last_login_at / last_login_ip / created_at。

**权限清单（`PERM_GROUPS`，前端角色界面直接消费，前后端 key 一致）**

| 菜单 | 菜单权限 | 按钮权限 |
|---|---|---|
| 经营驾驶舱 | dashboard.view | dashboard.config（配置转化概率） |
| 项目管理 | market.view | market.detail / market.edit / market.import / market.delete |
| 任务管理 | task.view | task.detail / task.edit / task.delete / task.import |
| 指标维护 | metric.view | metric.edit_company / metric.edit（维护监控指标）/ metric.edit_project / project.create/edit/delete / metric.import |
| 账号管理 | account.view | account.edit / account.role / account.import / account.delete |
| **系统配置·数据字典** | **sys.config.view** | **sys.config.edit** |
| **下载中心** | **download.view** | （仅查看/下载/删除自己生成的记录，无独立按钮权限） |

`DEFAULT_PERMS_FOR_ALL = ["task.detail", "market.detail", "sys.config.view", "download.view"]`（所有角色含「查看详情/数据字典/下载中心」，普通成员默认可读自己的导出记录，但导出行为由业务接口触发，不在此菜单权限外额外开放）。

### 5.7 市场项目与车头/挂车需求（Round 23 核心）

**`market_project`（汇总快照表）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(32) PK | MP0001+ |
| name / description | str / text | 项目名称 / 描述 |
| progress | text | **最新一条进展冗余快照**（= 最近一次 ProjectProgress.content） |
| tractor_demand / trailer_demand | int | **车头/挂车需求数量汇总**（= 明细 qty 之和，供列表列与漏斗复用） |
| stage | int (index) | 10/25/50/75/90/100 |
| owner | varchar(32) | 负责人姓名 |
| owner_dept_id | varchar(16) FK→organization (SET NULL) | 负责人直接部门（选负责人后自动带出） |
| created_by / created_at / updated_at | | 审计 |

**`project_tractor_requirement` / `project_trailer_requirement`（明细子列表，结构相同）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK 自增 | |
| project_id | varchar(32) FK→market_project | 级联删除 |
| model | varchar(64) | 车辆型号 / 挂车型号（取自数据字典） |
| battery | varchar(32) | 电池度数 |
| qty | int | 数量（辆） |

**关键设计点（K-1~K-7）**
- **K-1 列头表格**：编辑/详情表单的车头、挂车需求改为标准表格，列头直接展示「车辆型号 / 电池度数 / 数量 / 操作」，下方为可增删的行。
- **K-2 汇总冗余**：`tractor_demand`/`trailer_demand` 存明细 qty 之和；列表「车头数量/挂车数量」与驾驶舱漏斗直接读汇总值，**不**逐行聚合，口径稳定。
- **K-3 明细可追溯**：`project_*_requirement` 保存每行型号/度数/数量；详情弹窗与编辑表单展开明细，比值与汇总一致。
- **K-4 整份替换**：编辑提交时 `_reconcile_requirements` 先删后插，子列表增删即全量覆盖。
- **K-5 阶段固定**：stage 取值固定 10/25/50/75/90/100，后端 `require_perm` + 前端下拉双控。
- **K-6 数据权限**：列表/详情/编辑按创建人归属部门匹配可见范围（与任务模块一致）；驾驶舱漏斗仅按角色权限，不做范围裁剪。
- **K-7（已移除）重新生成**：原 `POST /market-projects/reseed` 整库种子数据重建入口已删除，「项目管理」不再提供「重新生成」按钮；演示环境重置改由部署侧 `SEED_RESET=1 sh start.sh` 完成。

### 5.8 系统配置·数据字典（Round 23 新增）

**`sys_dict`（一级）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK 自增 | |
| code | varchar(64) unique, nullable | 固定编码，如 `vehicle_model` / `trailer_model`；无编码时仅按 id 维护 |
| name | varchar(64) | 字典名称 |
| created_at / updated_at | datetime | 审计 |
| items | relationship→SysDictItem | cascade delete-orphan |

**`sys_dict_item`（二级枚举值）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK 自增 | |
| dict_id | int FK→sys_dict | |
| value | varchar(128) | 枚举值 |
| sort | int | 升序；返回时按 (sort, id) 排序 |

**关键设计点（S-1~S-6）**
- **S-1 两级结构**：字典（一级，可带 code）+ 枚举值（二级）；车辆型号 `vehicle_model`、挂车型号 `trailer_model` 为种子预设。
- **S-2 按 code 取值**：前端按 `code` 拉字典填充项目需求子列表的下拉项；无 code 的字典仅供后台维护。
- **S-3 种子预设**：`seed.py` 预置 `车辆型号 = [6*4牵引车, 4*2牵引车, 矿卡, 自卸车]`、`挂车型号 = [侧翻挂, 高栏挂, 后翻挂]`。
- **S-4 CRUD + 整份替换枚举**：`PATCH` 时枚举值整份删除后重插（支持增删多行）。
- **S-5 权限分级**：`sys.config.view` 所有角色默认可读（普通成员也能取型号下拉）；`sys.config.edit` 仅管理员可维护。
- **S-6 可维护**：界面提供字典列表/新增/编辑/删除，编码唯一约束（重名 422）。

### 5.9 `operation_log` 操作日志

`id(bigserial) / user_id / action / target_type / target_id / detail(json) / ip / created_at`

### 5.10 `funnel_config` 漏斗转化概率

单行单阶段（stage PK / prob float）；缺省时按阶段百分比回落（见 `services.funnel`）。

### 5.11 `download_record` 下载中心记录（Round 24 新增）

导出文件先落盘并在本表生成记录（**导出端点只返回该记录 JSON，不再即时返回文件流**，实际文件由用户在下载中心按记录下载）；列表与文件下载/删除均按 `created_by` 隔离（仅本人可见可操作）。文件存放于 `settings.download_dir`（默认 `backend/downloads/`，`.gitignore` 排除，不进源码仓库）。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | Integer PK 自增 | | 导出记录 ID（列表列「记录ID」） |
| object_type | String(32) | index | 导出对象类型：`task`（重点任务）/ `market_project`（市场项目） |
| filename | String(128) | | 自动生成的导出文件名，即下载文件名 |
| created_by | String(16) | FK→user.id, index | 创建人账号（列表列「创建人」） |
| created_at | DateTime | server_default func.now(), index | 创建时间（列表列「创建时间」） |

**关键设计点（X-1~X-6）**

- **X-1 落盘即记录**：`tasks/export` 与 `market-projects/export` 改为先调用 `create_download_record(db, user, object_type, content)` → 写文件 + 建记录（调用方 commit），再返回 `DownloadRecordOut`（记录 JSON，**不再返回文件流**）。前端导出后 toast 提示「已生成导出记录，请前往下载中心下载」并跳转下载中心。
- **X-2 文件命名**：`{对象中文标签}_{YYYYMMDD_HHMMSS}.xlsx`（如 `重点任务_20261017_153000.xlsx`、`市场项目_20261017_153500.xlsx`）；同名追加序号（`.xlsx` → `_1.xlsx`）。标签来自 `_OBJECT_LABELS = {"task":"重点任务","market_project":"市场项目"}`。
- **X-3 对象枚举**：`object_type` 仅 `task` / `market_project` 两值，与导出端点一一对应；后续新增导出对象只需扩 `_OBJECT_LABELS` 与枚举。
- **X-4 数据隔离**：列表 `GET /downloads` 强制 `created_by == user.id`；`GET /downloads/{id}/file` 与 `DELETE /downloads/{id}` 二次校验 owner，非本人 403。
- **X-5 删除语义**：删除记录同步 `os.remove` 落盘文件（文件缺失仅删记录，不报错）。
- **X-6 权限与默认角色**：菜单权限 `download.view` 加入 `DEFAULT_PERMS_FOR_ALL`，所有角色（含普通成员）默认可进「下载中心」看自己生成的记录；导出动作本身仍受原业务接口权限（`task.view` / `market.view`）约束，下载中心不另设写权限。

---

## 6. 关键接口设计

统一前缀 `/api/v1`。响应：`{ "data": ... }`；错误 `{ "detail": "...", "code": "..." }`。
状态码：200 / 201 / 400 / 401 / 403 / 404 / 409 / 422 / 500。

### 6.1 鉴权

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | `{account, password}` → `{access_token, user, perms[], scope}` |
| POST | `/auth/logout` | 前端清 Cookie |
| GET | `/auth/me` | 当前用户与权限范围 |
| GET/PUT | `/auth/preferences` | 用户偏好（行高记忆等，白名单 `rowHeight`） |

### 6.2 组织 / 项目公司

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/orgs?flat=0` | 组织树（含 depth）；`flat=1` 扁平 |
| POST/PATCH/DELETE | `/orgs/{id}` | 新增/改名/删除（市场部 D01 锁定不可删） |
| GET | `/projects` | 项目公司列表 |
| POST/PATCH/DELETE | `/projects/{id}` | 增改删（权限 `project.*`；删除上归并引用） |

### 6.3 角色 / 账号

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/permissions` | 权限清单（PERM_GROUPS）+ 范围选项 |
| GET | `/roles` / POST / PATCH / DELETE | 角色管理（内置或有关联账号 → 409） |
| GET | `/users` / POST / PATCH / POST status | 账号管理；`scope` 必填四档之一（空值 422） |
| GET | `/users/import/template` / POST `/users/import` | 批量导入（任一行出错整批不写） |
| GET | `/users/{id}/impact` / DELETE | 删除前预检六类引用；禁止删自己与最后管理员 |

### 6.4 指标 / 任务 / 任务组

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/metrics/defs` `/metrics/periods` `/metrics/board` | 指标定义 / 周期 / 维护页一次性数据 |
| PUT | `/metrics/targets` `/metrics/actuals` | upsert |
| GET | `/tasks` `/tasks/{id}` `/tasks/{id}/progress` | 列表（按范围过滤）/ 详情 / 进展时间轴 |
| POST/PATCH/DELETE | `/tasks` `/tasks/{id}` | 新建（自动 ID、进展必填）/ 编辑（进展只追加）/ 删除（级联进展） |
| GET/POST/PATCH | `/task-groups` `/task-groups/{id}` | 任务组字典（改名 ID 不变） |

### 6.5 项目管理 / 系统配置（Round 23）

**项目管理（市场项目，前缀 `/market-projects`）**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | ``（列表） | 服务端按可见范围过滤；`stage` 为空必须不传 |
| GET | `/export` | 导出可见项目：生成 xlsx 落盘并在下载中心建记录，返回 `DownloadRecordOut`（不即时下载，由用户在下载中心取文件） |
| GET | `/{id}` | 详情（范围外 403）；带出 `tractorRequirements`/`trailerRequirements` 明细 |
| POST | `` | 新建，`tractor_demand=Σ tractorRequirements.qty`，整份写明细 |
| PATCH | `/{id}` | 编辑；`tractor_demand`/`trailer_demand` 重算；明细整份替换 |
| DELETE | `/{id}` | 级联删除进展与需求明细 |
| GET/POST | `/{id}/progress` | 项目进展时间轴（最新一条冗余到 `progress`） |
| GET | `/import/template` / POST `/import` | 导入模板 6 列；校验失败整批回滚 |

**系统配置·数据字典（前缀 `/system/dicts`）**

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | ``（可 `?code=`） | sys.config.view |
| POST | `` | sys.config.edit（编码唯一，重名 422） |
| PATCH | `/{id}` | sys.config.edit（枚举整份替换） |
| DELETE | `/{id}` | sys.config.edit（级联删枚举） |

**下载中心（前缀 `/downloads`，权限 `download.view`）**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | ``（列表） | 当前用户本人导出记录，按 `created_at.desc()`；响应 `list[DownloadRecordOut]`（id / objectType / filename / createdById / createdByName / createdAt） |
| GET | `/{id}/file` | 下载文件（`FileResponse`）；校验 `created_by==user.id`，否则 403；文件不存在 404 |
| DELETE | `/{id}` | 删除记录（204），校验 owner，删记录并 `os.remove` 落盘文件 |

> 导出触发端点（`GET /tasks/export`、`GET /market-projects/export`）仍走原业务权限（`task.view` / `market.view`），在返回前落盘 + 建记录（X-1），但**只返回记录 JSON（`DownloadRecordOut`），不再返回文件流**；实际文件由用户在下载中心按记录点击「下载」获取。下载中心仅做「记录列表 / 重新下载 / 删除」，不直接触发导出。

### 6.6 经营驾驶舱 / 漏斗

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/dashboard/summary` | 综合达成率、时间进度、风险与建议 |
| GET | `/dashboard/overview` | 年度/项目/监控三段 + 项目对比 |
| GET | `/dashboard/dept-task-stats?period=&filter=` | 部门任务完成度（filter: all/year/month/open） |
| GET | `/dashboard/project-funnel` | 市场项目概览：六层「当前阶段」漏斗 + 加权销量预测 |
| GET/PUT | `/dashboard/funnel-config` | 各阶段转化概率（PUT 需 dashboard.config） |
| GET | `/dashboard/metrics/{id}/trend` 与 `/trends?ids=` | 单指标/批量趋势 |

---

## 7. 状态流转

- **登录态**：未登录 →（登录成功）→ 已登录 →（过期/登出）→ 未登录。前端 401 拦截跳转登录页。
- **账号**：active ⇄ disabled（disabled 不可登录）。
- **任务**（由数据推导，无手工状态字段）：未完成 → 逾期/临期/正常（叠加 abnormal → 异常）；done≥target → 已完成（终态）。
- **指标**：无目标（监控）→ 不判定；有目标无实际 → 未录入；有目标有实际 → 按 `progress_tone` 五档（done/ahead/near/risk/none）。
- **市场项目阶段**：10→25→50→75→90→100 固定推进，不强制顺序。

---

## 8. 错误处理

| 分类 | 场景 | 处理 |
|---|---|---|
| 可重试 | 网络抖动、超时 | 前端提示并保留输入 |
| 不可重试 | 401/403/409/422 | 401 跳登录；403 提示无权限；409/422 展示服务端消息 |
| 数据 | 除零（目标 0 / 收入 0） | 达成率/回款率返回 `null`，前端显示「—」 |
| 导入 | 存在错误行 | 全量校验后统一返回错误明细，不写脏数据 |
| 枚举整份替换 | 编辑字典 | 先删后插，保证最终态与提交一致 |

---

## 9. 权限、安全与隐私

- **最小权限**：菜单权限控制入口可见性，按钮权限控制操作；服务端为最终裁决（`require_perm`）。
- **数据隔离**：`visible_org_ids(user)` / `visible_task_filter` / `visible_market_project_filter` 依据 `effective_scope` 计算；列表接口强制注入范围过滤。
- **可见任务**：`任务所属组织 ∈ 可见组织` **OR** `责任人 = 本人姓名`（兜底）。
- **密码**：bcrypt 加盐哈希；接口与日志不返回 `password_hash`。
- **令牌与线上鉴权坑（重要）**：JWT（HS256），支持 Authorization Bearer 与 HttpOnly Cookie。线上网关会**改写 `Authorization` 头**（用自身令牌覆盖客户端令牌），导致 Bearer 失效。解析器改为「头优先、Cookie 兜底」：依次尝试候选令牌，取第一个可正确解码者。验证接口须走登录下发的 Cookie（`access_token`），Bearer 头会被覆盖。
- **审计**：登录、录入、修改、删除、导入写 `operation_log`（含 IP）。
- **配置**：数据库连接、JWT 密钥等全部环境变量外置，代码零硬编码。
- **越权防护**：前端隐藏按钮不作为安全边界；所有写接口二次校验权限与数据归属。

---

## 10. 性能与降级

| 关注点 | 措施 |
|---|---|
| 聚合 | 驾驶舱加权汇总、部门任务完成度在 SQL 层 GROUP BY |
| 索引 | `metric_actual(metric_id, org_id, period)`、`market_project(stage)`、`owner_dept_id` 等 |
| N+1 | 一次查询取定义+目标+实际；列表 enrichment 批量去重查（创建人/部门/进展/需求） |
| 前端 | 路由懒加载（每视图独立 chunk）；驾驶舱一次请求返回 |
| 压缩/缓存 | `GZipMiddleware`；静态资源 `Cache-Control: immutable`，`index.html` `no-cache` |
| 导入 | 单文件 ≤ 5MB、单次 ≤ 2000 行 |
| 扩展 | 鉴权无状态，API 可水平扩容；SQLite 下连接池退化为单连接（check_same_thread=False） |

---

## 11. 目录结构与部署

```
.
├── docs/                         # 规范文档
│   ├── proposal.md  design.md  test-report.md
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口（挂载 /api + 托管 static）
│   │   ├── config.py            # 环境变量配置（is_sqlite 分支）
│   │   ├── db/{base,session}.py
│   │   ├── core/{security,deps}.py
│   │   ├── models/              # organization/metric/task/task_group/user/role/
│   │   │                       #   market_project + 需求明细 + 进展 + 字典 + funnel_config + download_record
│   │   ├── schemas/             # Pydantic v2
│   │   ├── services/            # achievement/scope/summary/importer/audit/download
│   │   ├── api/v1/              # auth/orgs/projects/roles/users/metrics/tasks/
│   │   │                       #   dashboard/market/system/downloads
│   │   ├── constants.py         # PERM_GROUPS / SCOPES / 阶段常量
│   │   └── seed.py              # 演示数据 + 数据字典预设
│   ├── tests/                   # pytest（153 passed）
│   ├── downloads/               # 导出文件落盘目录（gitignore，不进仓库）
│   ├── static/                  # 前端构建产物（发布时同步进来，gitignore）
│   ├── requirements.txt
│   └── start.sh                 # 启动入口：seed → uvicorn（监听 $PORT，0.0.0.0）
├── frontend/
│   ├── src/{api,stores,router,layouts,views,components,styles,types}
│   ├── index.html  vite.config.ts  tailwind.config.js  tsconfig.json
└── README.md / 交付说明.md / 交接说明.md
```

**发布方式（当前线上）**：WorkBuddy `sites` 发布，目录 `backend/`、language=python、startCmd `bash start.sh`、domainPrefix `heyi-fleet-dashboard`。线上地址 `https://heyi-fleet-dashboard.app.workbuddy.host/`。`start.sh` 默认幂等 seed（已有数据不动），`SEED_RESET=1` 可重置回初始演示态。发布前前端 `npm run build` 产物同步进 `backend/static`。

> 注：早期方案中的 `deploy/docker-compose.yml` + Nginx 反代已不再是发布链路。代码仍兼容 PostgreSQL（改 `DATABASE_URL` 即可），但默认与线上均为 SQLite 单文件。

---

## 12. 需求—方案对应关系

| 需求编号 | 承担模块 | 设计章节 |
|---|---|---|
| A-1~A-4 登录与会话 | `auth` / `security` / `deps` | §6.1, §7, §9 |
| O-1~O-5 组织管理 | `orgs` / `scope` | §5.1, §6.2 |
| R-1~R-4 角色权限 | `roles` / `PERM_GROUPS` | §5.6, §6.3, §9 |
| U-1~U-5 账号管理 | `users` | §5.6, §6.3, §9 |
| M-1~M-15 指标维护 | `metrics` / `achievement` / `importer` | §5.2–5.4, §6.4, §8 |
| T-1~T-12 任务管理 | `tasks` / `importer` / `task_group` | §5.4–5.5, §6.4, §7 |
| D-1~D-43 经营驾驶舱 | `dashboard` / `summary` / `achievement` | §4, §5.2, §6.6, §10 |
| I-1~I-6 数据导入 | `importer` | §4, §6.4–6.5, §8 |
| **K-1~K-7 项目管理车头/挂车需求子列表** | `market-projects` / `project_*_requirement` | §5.7, §6.5 |
| **S-1~S-6 系统配置·数据字典** | `system/dicts` / `sys_dict` / `sys_dict_item` | §5.8, §6.5 |
| **X-1~X-6 下载中心** | `downloads` / `download_record` / `services.download` | §5.11, §6.5 |
| **E-15~E-17 异常与校验** | 各接口 | §8 |

---

## 13. 变更记录（精选）

> v2.0 起技术栈以现状为准（SQLite 单文件 + 单端口同源托管）；以下精选仍具决策价值的记录，旧文档中的 PostgreSQL/Docker 描述已作废。

- **2026-10-12 · 编辑权限分块（M-19）**：`metric.edit` 语义收敛为「维护监控指标」，与公司整体目标（`metric.edit_company`）、项目公司（`metric.edit_project`+`project.*`）三块独立，无隐含前置权限。
- **2026-10-13 · 状态口径统一（M-14/15）**：单指标状态统一为 `progress_tone(rate, time_progress)` 五档；整体结论 `verdict` 复用同函数（done/ahead→good、near→warn、risk→bad、none→none），文案与时间进度挂钩。
- **2026-10-13 · 数据权限边界（D-15~17）**：仅任务模块按可见范围隔离；驾驶舱与指标维护只按角色权限（全公司口径），因全公司与项目公司非递归汇总关系。
- **2026-10-14 · 市场项目模块（D-30~33）**：新增市场项目与驾驶舱漏斗；漏斗口径由累计改为「当前阶段」，销量预测按阶段概率加权；条形图式漏斗造型。
- **2026-10-15 · 市场部锁定 + 漏斗按二级部门筛选 + 负责人限定 + 重生成（D-40~43）**：D01 锁定；漏斗 `dept_id` 过滤；负责人下拉仅市场子树；`reseed` 确定性造数（修复 autoflush 下 ID 重复）。
- **2026-10-15 · 任务组字典（round15/16）**：任务分类升级为独立 `task_group` 表，责任人/部门首次选用时回填；分组视图按任务组 ID 归类。
- **2026-10-16 · 任务进展时间轴（round18）**：`task_progress` 表，编辑只追加；`task.detail` 全角色可见。
- **2026-10-16 · 列宽固定 + 省略号 + 行高偏好（round19/20）**：用户偏好持久化；`table-fixed` + `.cell-c` 真正固定列宽与省略号。
- **2026-10-17 · Round 23 系统配置·数据字典 + 项目管理车头/挂车需求子列表（K/S）**：新增 `sys_dict`/`sys_dict_item`（种子预设车型）；`project_tractor_requirement`/`project_trailer_requirement` 明细表 + `tractor_demand`/`trailer_demand` 汇总快照；编辑表单改为列头表格；项目导入模板精简为 6 列（不含车辆需求，车辆需求在系统内补充）；导出含汇总列。详见 `proposal.md` §5.8–5.10。
- **2026-10-17 · Round 24 下载中心（X-1~X-6）**：新增 `download_record` 表与 `services/download.py`；`tasks/export`、`market-projects/export` 改为「先落盘建记录再返回文件」；新增 `GET /downloads`（列表）、`GET /downloads/{id}/file`（下载）、`DELETE /downloads/{id}`（删除），均按 `created_by` 隔离（仅本人可见可操作）；菜单权限 `download.view` 纳入 `DEFAULT_PERMS_FOR_ALL`；前端新增「下载中心」菜单与 `DownloadsView` 列表页，导出后 toast 引导去下载中心。需求文档同步去掉「典型人员」虚拟角色列（`proposal.md` v3.1）。后端测试 149 → **153 passed**（新增 `test_downloads.py` 4 项）。详见 `proposal.md` §3.13、§5.13。
- **2026-10-17 · Round 26 导出口径收紧 + 移除重新生成**：`tasks/export`、`market-projects/export` 改为「落盘建记录后只返回 `DownloadRecordOut`，不再返回文件流」，前端导出后跳转下载中心由用户取文件；删除 `POST /market-projects/reseed` 及前端「重新生成」按钮（演示重置改由部署侧 `SEED_RESET=1` 完成）。测试随语义改写，当前 **152 passed**。
- **2026-10-17 · Round 27 菜单归并 + 任务组全栈重命名**：前端 `AppLayout.vue` 的「账号管理」「下载中心」由与「系统配置」平级的顶级菜单移入其 `children`（与「数据字典」并列），权限点 `account.view`/`download.view` 不变；任务管理「主任务」全栈更名为「任务组」——模型 `MainTask`→`TaskGroup`（表 `main_task`→`task_group`）、`Task.main_task_id`→`task_group_id`、`importer`/`achievement` 的 `MT_NONE_ID`/`MT(\d+)`→`TG_NONE_ID`/`TG(\d+)`、API `/main-tasks`→`/task-groups`（模块 `main_tasks.py`→`task_groups.py`，`router.py` 同步改引用）、前端 `api/index.ts`/`TasksView.vue` 的 `mainTask*`/`MT_NONE_ID`→`taskGroup*`/`TG_NONE_ID`、种子与测试（`test_main_tasks.py`→`test_task_groups.py`）同步；启动迁移（`app/main.py` lifespan 与 `app/seed.py` main）均处理 `main_task`→`task_group` 的 RENAME。演示库经 `SEED_RESET=1 bash start.sh` 硬重置（start.sh 在 `SEED_RESET=1` 时先删库文件再重建）统一为 `TG` 前缀 ID。后端测试仍为 **152 passed**（纯重命名，无新增用例）。
- **2026-10-18 · Round 28 责任人默认与范围过滤 + 任务组联合唯一与删除 + 字段长度限制 + 项目描述必填**：① 责任人下拉范围按 `effective_scope`（账号 scope 覆盖角色 scope）过滤——新增 `services/scope.py:visible_user_filter`，`api/v1/meta.py:owner_options` 仅返回范围内已启用账号；前端 `TasksView.openForm` 新建默认 `owner=auth.user.name`，编辑时若责任人不在下拉则追加。② 任务组唯一性由库级 `name` 唯一改为「名称 + owner_id」联合唯一（接口层校验），同名不同责任人允许并存；`models/log.py:TaskGroup.name` 去 `unique`，`main.py` 启动时迁移 `DROP CONSTRAINT` 去掉旧唯一索引（失败兜底整表重建）；`task_groups.py` 新增 `owner_id` 入参与 `DELETE /task-groups/{id}`（有引用任务回退 `TG_NONE`，`is_system` 不可删）。③ 字段长度全栈限制——`schemas/task.py`（任务名 40/描述 150/进展 150）、`schemas/project.py`（项目名 40/描述 150/进展 150）、`task_groups.py`（任务组名 25）加校验器；`services/importer.py` 导入时校验长度与必填；前端 `TasksView`/`ProjectsView` 加 `maxlength` 与保存校验、任务组下拉加宽（`w-80`）并支持删除。④ 项目描述改为必填（`schemas/project.py` 非空校验 + `importer` + 前端 label/save 一致）。后端测试仍为 **152 passed**（纯约束收紧，无新增用例）。

---

## 14. 测试与质量门禁

- **后端**：`pytest tests/`，当前 **152 passed**（详见 `test-report.md`）。
- **前端**：`npm run build`（`vue-tsc --noEmit` 类型检查 + `vite build`），当前通过（含 `DownloadsView` chunk）。
- **线上验证**：发布后对公开链接复跑接口与浏览器验收，确认鉴权（Cookie 通道）、字典取值、需求子列表、漏斗口径、下载中心记录一致。

## 15. 已知限制与后续项

| 项 | 说明 |
|---|---|
| 数据库 | 演示用 SQLite；生产如需更高并发可切 PostgreSQL（改 `DATABASE_URL`） |
| 导入模板 | 项目导入 6 列不含车辆需求，车辆需求在系统表单补充；导出为超集（含汇总列），可直接回灌 |
| 审计 | 已落库，可接企业 SIEM |
| 多实例 | 鉴权无状态可水平扩容；SQLite 下为单写，需多写再切 PG |
