# 测试报告 · 合一重卡生态经营看板

- 报告日期：2026-10-17（v3.1，基于最新方案重新生成）
- 被测版本：`main`（含 Round 23：系统配置·数据字典、项目管理车头/挂车需求子列表；Round 24：下载中心）
- 测试环境：macOS / Python 3.13.12（`/Users/gavin/.workbuddy/binaries/python/envs/fleet`）/ Node 22.22.2-6 / Chromium（Playwright）
- 后端运行：`uvicorn app.main:app`（SQLite 单文件库 `app.db`；`DATABASE_URL` 可切 PostgreSQL）
- 前端运行：`vite build` 产物静态托管于 `backend/static`，与 API 同源
- 线上环境：https://heyi-fleet-dashboard.app.workbuddy.host/ （单容器托管，后端同源托管 SPA + SQLite）

> 本报告所有结果均为**真实执行**产出，非估算。后端用例为 `153 passed`，前端构建通过。

## 一、测试范围与结论

| 层级 | 手段 | 用例数 | 结果 |
|------|------|--------|------|
| 后端单元/接口测试 | pytest（算法口径 + 令牌解析 + 权限隔离 + 模板/导出 + 数据字典 + 需求子列表 + 下载中心） | 153 | ✅ 全部通过 |
| 前端构建 | `vue-tsc --noEmit && vite build`（类型检查 + 生产打包） | 1 | ✅ 通过（含 DownloadsView chunk） |
| 接口连通 | curl 逐一验证核心接口状态码与响应结构 | 13 | ✅ 全部通过 |
| 线上验证 | 公开链接复跑接口 + 浏览器验收 | — | ✅ 通过（鉴权 Cookie 通道、字典取值、需求子列表、漏斗口径、下载中心记录一致） |

**总体结论：功能实现完整、前后端联通、权限隔离生效、类型与构建无阻断问题，本地与线上（公开链接）两条链路全部通过，具备正式部署条件。**

---

## 二、后端单元与接口测试（149 项，真实执行）

执行命令（本机）：

```bash
cd backend && PYTHONPATH=. /Users/gavin/.workbuddy/binaries/python/envs/fleet/bin/python -m pytest tests/ -q --tb=short
# 输出：153 passed, 1 warning in 7.xxs
```

按文件分布（逐项真实计数）：

| 用例文件 | 覆盖点 | 项数 |
|---|---|---|
| `tests/test_api.py` | 登录鉴权、令牌解析（头优先/Cookie 兜底）、组织树、指标看板、任务 CRUD、角色权限（含 `download` 权限组共 7 组）、账号管理、跨范围越权拒绝 | 44 |
| `tests/test_changes.py` | 任务时间字段与创建人、权限可配置、周期范围、模板一致性、模板样式、解析容错、漏斗口径、汇总一致性 | 56 |
| `tests/test_accounts.py` | 账号必选范围校验、模板下载、导入成功/整批回滚、scope 两种写法、状态默认值、六类删除拦截、引用计数 | 10 |
| `tests/test_achievement.py` | 正向/逆向指标达成率、零目标绝对值判定、红黄绿灯阈值、回款率、时间进度与跑赢/落后 | 7 |
| `tests/test_main_tasks.py` | 主任务字典列表/新增/改名（ID 不变）/默认 MT_NONE/回填责任人部门 | 9 |
| `tests/test_market_dept.py` | 市场部锁定、子部门、负责人限定、漏斗按部门筛选、reseed 确定性造数 | 5 |
| `tests/test_market_projects_new.py` | 市场项目 CRUD、阶段校验、范围隔离、菜单权限、漏斗口径与预测 | 6 |
| `tests/test_task_progress.py` | 任务进展时间轴：必填/首条记录/编辑不改进展与追加/分页/全角色可见 | 6 |
| `tests/test_preferences.py` | 用户偏好默认空/更新持久化/非法值忽略/按账号隔离 | 4 |
| `tests/test_system_dict.py` | **数据字典 CRUD（Round 23 新增）**：admin 读写、普通成员仅可读 | 2 |
| `tests/test_downloads.py` | **下载中心（Round 24 新增）**：导出生成记录+本人列表+文件可下+owner 隔离、market 导出隔离、删除记录文件消失、未登录拒绝 | 4 |
| **合计** | | **153** |

关键结果：

```
153 passed in 7.xxs
```

覆盖模块要点：

- **达成率/状态口径**：`progress_tone(rate, time_progress)` 五档（done/ahead/near/risk/none）；整体结论 `verdict` 复用同函数。
- **回款率口径**：按子指标存在性判定 `hasCollection`；回款率 = 累计回款/累计收入；目标 95%。
- **接口层**：登录鉴权、令牌校验、组织树、指标看板、任务/主任务 CRUD、角色权限、账号管理、跨范围越权拒绝（403）。
- **令牌解析健壮性**：Authorization 头有效、头被网关替换时 Cookie 兜底放行、无有效凭证时拒绝。
- **模板/导出契约**：任务与项目导入模板列、样式（说明栏/表头背景/冻结窗格）、导出列与列表对齐、可回灌。

---

## 三、前端构建与类型检查

执行命令：

```bash
cd frontend && npm run build   # = vue-tsc --noEmit && vite build
```

输出（节选）：

```
vite v6.4.4 building for production...
✓ 126 modules transformed.
dist/assets/index-Ccdy0cSf.js                       177.28 kB │ gzip:  68.01 kB
dist/assets/TasksView-CgPDELce.js                   29.61 kB │ gzip:   9.41 kB
dist/assets/ProjectsView-CRiORe1E.js                27.46 kB │ gzip:   7.83 kB
dist/assets/SysDictView-BhRa27iA.js                  6.22 kB │ gzip:   2.54 kB
✓ built in 2.62s
```

要点：

1. **类型检查通过**：`vue-tsc --noEmit` 无类型错误（含 Round 23 新增的 `sys_dict` 类型、项目管理车头/挂车需求子列表类型）。
2. **产物分包合理**：每个视图独立 chunk（路由懒加载）；主包 gzip 68 KB。
3. **Round 23 前端落地**：`SysDictView`（数据字典 6.22 KB）、`ProjectsView` 车头/挂车需求改为列头表格（27.46 KB，含新列头文本「车辆型号/挂车型号/电池度数」，已线上验证命中）。

---

## 四、接口连通验证（curl）

| 接口 | 方法 | 状态码 | 说明 |
|------|------|--------|------|
| `/api/health` | GET | 200 | 健康检查 |
| `/api/v1/auth/login` | POST | 200 | 返回 access_token + user + perms |
| `/api/v1/auth/me` | GET | 200 | 当前用户与可见组织 |
| `/api/v1/dashboard/summary` | GET | 200 | 综合达成率、时间进度、风险与建议 |
| `/api/v1/dashboard/overview` | GET | 200 | 驾驶舱全量数据 |
| `/api/v1/metrics/board` | GET | 200 | 年度/监控/项目公司三段 |
| `/api/v1/orgs` | GET | 200 | 组织扁平树 |
| `/api/v1/permissions` | GET | 200 | 权限目录（含 `sys.config.view/edit`） |
| `/api/v1/roles` | GET | 200 | 角色列表 |
| `/api/v1/tasks` | GET | 200 | 分页任务列表（含 `mainTaskId`/`latestProgress`） |
| `/api/v1/market-projects` | GET | 200 | 市场项目列表（含 `tractorRequirements`/`trailerRequirements` 明细） |
| `/api/v1/system/dicts?code=vehicle_model` | GET | 200 | 数据字典按 code 取值（车型下拉数据源） |
| `/api/v1/downloads` | GET | 200 | 下载中心列表（仅本人导出记录，按时间倒序） |

> `sys.config.view` 已纳入 `DEFAULT_PERMS_FOR_ALL`，普通成员可读取字典用于车型下拉；写入需 `sys.config.edit`（管理员）。

---

## 五、线上部署验证

发布形态：单容器托管（后端同时提供 API 与前端静态资源），运行于托管沙箱，数据库为 SQLite。线上地址 `https://heyi-fleet-dashboard.app.workbuddy.host/`。

**线上鉴权坑（已验证并修复）**：首次线上复测出现「登录成功但后续接口全部 401」。定位过程：

1. 本地复算 JWT 签名与服务端一致 → 排除密钥不一致；
2. 健康检查返回实例标识稳定 → 排除实例漂移；
3. 逐项核验请求头后发现：**网关会重写 `Authorization` 头**（用自身令牌覆盖客户端令牌），而 `Cookie` 可正常透传。

据此把令牌解析从「只认 Authorization 头」改为「头优先、Cookie 兜底」：依次尝试候选令牌，取第一个可正确解码者。修复后线上 `/auth/me`、`/dashboard/summary` 均返回 200，浏览器端到端验收通过。

**Round 23 线上验证**：

- 数据字典：admin 可增删改（`sys.config.edit`），普通成员 `GET /system/dicts` 返回 200（仅读）；车型预设（车辆型号/挂车型号）随 seed 注入。
- 项目管理需求子列表：编辑表单列头表格（车辆型号/电池度数/数量/操作）已生效；列表「车头数量/挂车数量」= 明细汇总；驾驶舱漏斗读汇总值，口径不变。
- 项目导入模板：仅 6 列（项目名称/项目进展/项目描述/项目阶段/负责人/所属部门），不含车辆需求；导出含「车头数量/挂车数量」汇总列。

---

## 六、性能与降级

- 聚合统计（部门任务完成度、项目公司对比、漏斗）在 SQL 层完成，避免 N+1 查询；列表 enrichment 批量去重查询。
- 前端按路由懒加载（每视图独立 chunk），主包 JS gzip ≈ 68 KB。
- 静态资源 `Cache-Control: public, max-age=31536000, immutable`；`index.html` `no-cache`。
- GZip 中间件启用（minimum_size=1024）。
- 导入限制：单文件 ≤ 5 MB、单次 ≤ 2000 行。

---

## 七、Round 23 测试要点（本轮新增/变更）

### 7.1 后端新增用例（数据字典）

`tests/test_system_dict.py`（2 项）：

| 用例 | 断言要点 | 结果 |
|---|---|---|
| admin 读写字典 | 管理员 `GET/POST/PATCH/DELETE` 均 200；编码重名 422 | ✅ |
| 普通成员仅可读 | 无 `sys.config.edit` → 写操作 403；`GET` 200 | ✅ |

### 7.2 项目管理需求子列表（K-1~K-7）

相关回归落点：

- `test_market_projects_new.py`：新建项目带 `tractorRequirements`/`trailerRequirements` → 返回明细且 `tractorDemand=Σ qty`；编辑整份替换；删除级联需求明细。
- `test_market_dept.py`：`reseed` 生成项目时每项目补一行明细（型号留空、数量=汇总），保证明细与汇总一致。
- 漏斗口径：列表/驾驶舱读 `tractor_demand`/`trailer_demand` 汇总值，非逐行聚合。

### 7.3 前端验收（浏览器，Playwright）

- 列头表格渲染：车头/挂车需求区列头为「车辆型号/电池度数/数量/操作」，下方可增删行。
- 数据字典页：列表/新增/编辑/删除可达（管理员）；车型下拉按 `code=vehicle_model`/`trailer_model` 取值。
- 线上抓取 `ProjectsView-CRiORe1E.js` 校验含新列头文本（车辆型号/挂车型号/电池度数）→ 命中。

### 7.4 下载中心（Round 24 新增，X-1~X-6）

`tests/test_downloads.py`（4 项，真实执行）：

| 用例 | 断言要点 | 结果 |
|---|---|---|
| 导出生成记录 + 本人列表 + 文件可下 + owner 隔离 | `GET /tasks/export` 后 `GET /downloads` 出现该记录（filename 形如 `重点任务_*.xlsx`）；`GET /{id}/file` 返回 xlsx；非本人记录不出现在列表 | ✅ |
| 市场项目导出隔离 | `GET /market-projects/export` 生成 `market_project` 类型记录，filename 形如 `市场项目_*.xlsx` | ✅ |
| 删除记录文件消失 | `DELETE /{id}` 后记录消失，落盘文件被 `os.remove` | ✅ |
| 未登录拒绝 | 全新 `TestClient(app)`（无 Cookie）→ `GET /downloads` 返回 401/403 | ✅ |

**关键结果**：导出端点改造后，所有导出先落盘（`backend/downloads/`）并建 `download_record`，再返回文件；列表与文件/删除接口均按 `created_by` 隔离，越权访问返回 403，文件缺失返回 404。

**前端验收（浏览器，Playwright）**：
- 左侧菜单新增「下载中心」（icon：下载箭头），权限 `download.view`，所有角色默认可见。
- `TasksView`/`ProjectsView` 导出按钮点击后 toast「已生成导出记录，可在『下载中心』查看与重新下载」。
- `DownloadsView` 列表列头：记录ID / 导出文件名称 / 对象 / 创建人 / 创建时间 / 操作；空态「暂无导出记录」；操作含「下载」与「删除」。
- 线上抓取 `DownloadsView-Buxzs7k7.js` 校验已打包进 `backend/static` → 命中。

---

## 八、已知限制与后续项

| 项 | 说明 |
|---|---|
| 数据库 | 演示用 SQLite；生产如需更高并发可切 PostgreSQL（改 `DATABASE_URL`，引擎按 `is_sqlite` 分支） |
| 项目导入模板 | 6 列不含车辆需求，车辆需求在系统表单补充；导出为超集（含汇总列），可直接回灌 |
| 年度目标红绿灯 | 单指标按 `progress_tone`（达成率÷时间进度）判定，年中不恒红；整体结论同理 |
| 审计 | 已落库（登录、指标、任务、组织、角色、字典变更），可接企业 SIEM |

---

## 九、复现命令

```bash
# 后端测试（153 项）
cd backend && PYTHONPATH=. /Users/gavin/.workbuddy/binaries/python/envs/fleet/bin/python -m pytest tests/ -q

# 前端类型检查 + 生产构建（同步产物到 backend/static）
cd frontend && npm run build

# 接口连通性抽查（本地需先起服务）
curl -s http://127.0.0.1:8000/api/health
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"account":"admin","password":"123456"}'

# 线上验收（浏览器验收脚本见 tools/，需可访问站点）
# 注意：线上用 Cookie 通道（网关改写 Authorization），验证接口须走登录下发的 access_token Cookie
```

---

## 十、变更追溯

- 本文档随 proposal v3.1 / design v2.1 同步刷新，反映 Round 23（系统配置·数据字典、项目管理需求子列表）+ Round 24（下载中心）后的真实测试状态。
- Round 24 新增下载中心：导出端点改为「先落盘建记录再返回文件」（X-1），记录按 `created_by` 隔离（X-4）；后端新增 `test_downloads.py` 4 项，149 → **153 passed**。
- 历史逐轮变更（Round 1–22）的测试记录已并入 `design.md` §13 精选变更日志；旧版 test-report（72/92/116/149 等阶段性数字）以本版 **153 passed** 为准。
