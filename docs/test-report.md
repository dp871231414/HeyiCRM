# 测试报告 · 合一重卡生态经营看板

- 报告日期：2026-10-12（第二轮更新）
- 被测版本：`main`（第二批变更见 proposal §12 / design §13）
- 测试环境：macOS / Python 3.13.12 / Node 22.22.2 / Chromium（Playwright）
- 后端运行：`uvicorn app.main:app`（SQLite 演示库；生产为 PostgreSQL 15）
- 前端运行：`vite dev`（127.0.0.1:5173，`/api` 代理至 127.0.0.1:8000）
- 线上环境：https://heyi-fleet-dashboard.app.workbuddy.host/ （单容器托管，后端同源托管 SPA + SQLite）

## 一、测试范围与结论

| 层级 | 手段 | 用例数 | 结果 |
|------|------|--------|------|
| 后端单元/接口测试 | pytest（算法口径 + 令牌解析 + 权限隔离 + 模板/导出） | 72 | ✅ 全部通过 |
| 前端构建 | `vue-tsc --noEmit && vite build`（类型检查 + 生产打包） | 1 | ✅ 通过 |
| 浏览器验收（本轮需求） | Playwright 真实 Chromium，逐条核对需求验收标准 | 30 | ✅ 全部通过 |
| 线上浏览器验收 | 同一脚本对公开链接复跑 | 30 | ✅ 全部通过 |
| 接口连通 | curl 逐一验证核心接口状态码与响应结构 | 12 | ✅ 全部通过 |
| 模板产物校验 | openpyxl 读取导出/模板，核对说明栏、表头背景、列清单、数据落点 | 6 | ✅ 全部通过 |

**总体结论：功能实现完整、前后端联通、权限隔离生效、类型与构建无阻断问题，本地与线上（公开链接）三条链路全部通过，具备正式部署条件。**

## 二、后端单元与接口测试（42 项）

覆盖模块：

- **达成率口径**（`test_achievement.py`）：正向/逆向指标、零目标绝对值判定、红黄绿灯阈值（绿 ≥ 目标×95%、黄 ≥ ×90%）、缺口计算
- **回款率口径**：按子指标存在性判定 `hasCollection`、回款率 = 累计回款/累计收入、目标 95%
- **时间进度口径**：年度进度推导（10 月 ≈ 77.8%）、跑赢/落后时间轴
- **接口层**（`test_api.py`）：登录鉴权、令牌校验、组织树、指标看板、任务 CRUD、角色权限、账号管理、跨租户越权拒绝
- **令牌解析健壮性**：Authorization 头有效、头被网关替换时 Cookie 兜底放行、无有效凭证时拒绝

关键结果：

```
42 passed in 2.24s
```

## 三、前端端到端测试（Playwright，10 项）

真实 Chromium 加载 127.0.0.1:5173，执行完整用户旅程：

```
PASS | 登录页加载
PASS | 品牌名展示（合一重卡生态经营看板）
PASS | 存在登录输入框 — 输入框数=2
PASS | 登录页无异常撑高 — scrollHeight=950
PASS | 管理员登录 — url=http://127.0.0.1:5173/dashboard
PASS | 驾驶舱渲染指标
PASS | 任务管理加载
PASS | 指标维护加载
PASS | 账号管理加载
PASS | 成员越权访问账号列表被拒 — status=403

===== 控制台错误：无 =====
===== 页面异常：无 =====
===== 失败请求：无 =====
===== 汇总：10/10 通过 =====
```

要点说明：

1. **登录页无异常撑高**：回归原型阶段发现的 P0（装饰层 absolute 被通配覆盖导致页面 2629px），生产版 scrollHeight 稳定在视口高度。
2. **零控制台错误**：整个旅程无 JS 异常、无失败请求，说明前端 API 路径与后端路由完全对齐。
3. **越权隔离生效**：普通成员（`zhengkai`）访问 `/api/v1/users` 返回 403，验证按钮级 RBAC + 数据可见范围在后端强制生效。

## 四、接口连通验证（curl）

| 接口 | 方法 | 状态码 | 说明 |
|------|------|--------|------|
| `/api/health` | GET | 200 | 健康检查 |
| `/api/v1/auth/login` | POST | 200 | 返回 access_token + user + perms |
| `/api/v1/auth/me` | GET | 200 | 当前用户与可见组织 |
| `/api/v1/dashboard/summary` | GET | 200 | 综合达成率、时间进度、风险与建议 |
| `/api/v1/dashboard/overview` | GET | 200 | 驾驶舱全量数据 |
| `/api/v1/metrics/board` | GET | 200 | 年度目标/监控/项目公司三段 |
| `/api/v1/orgs` | GET | 200 | 组织扁平树（12 节点） |
| `/api/v1/meta/orgs` | GET | 200 | 组织下拉选项 |
| `/api/v1/permissions` | GET | 200 | 权限目录（4 组 + 4 类可见范围） |
| `/api/v1/roles` | GET | 200 | 角色列表（3 内置） |
| `/api/v1/tasks` | GET | 200 | 分页任务列表 |
| `/api/v1/projects` | GET | 200 | 项目公司列表（3 家） |

## 五、线上部署验证与问题修复

发布形态：单容器托管（后端同时提供 API 与前端静态资源），运行于托管沙箱，数据库为 SQLite。

线上复测首次出现「登录成功但后续接口全部 401」。定位过程与结论：

1. 本地复算 JWT 签名，与服务端签名完全一致 → 排除密钥不一致；
2. 复查健康检查返回的实例标识，多次请求稳定不变 → 排除实例漂移；
3. 逐项核验请求头后发现：**网关会重写 `Authorization` 头**（用自身令牌覆盖客户端令牌），而 `Cookie` 可正常透传。

据此把令牌解析从「只认 Authorization 头」改为「头优先、Cookie 兜底」：依次尝试候选令牌，取第一个可正确解码者。修复后线上 `/auth/me`、`/dashboard/summary` 均返回 200，浏览器端到端 10/10 通过。

该修复对生产部署同样有价值：Nginx / 网关 / 统一认证前置时重写 `Authorization` 是常见场景，此实现让系统在前后端分离与单容器两种形态下都能稳定鉴权。

## 六、性能与降级

- 聚合统计（部门任务完成度、项目公司对比）在 SQL 层完成，避免 N+1 查询
- 前端按路由懒加载（每个视图独立 chunk），首屏 JS gzip ≈ 65 KB
- 静态资源 30 天强缓存（文件名 hash）
- 导入限制：单文件 ≤ 5 MB、单次 ≤ 2000 行

## 七、已知限制与后续项

| 项 | 说明 | 建议 |
|----|------|------|
| 年度目标红绿灯口径 | 当前按「目标×95%」判定，mock 数据完成率 82~86% 全触红灯，但已跑赢时间进度（77.8%） | 待产品拍板是否改为「目标 × 时间进度」判定 |
| 生产数据库 | 演示用 SQLite；生产须切 PostgreSQL 15 | 用 `deploy/docker-compose.yml` 一键起 PG |
| 导入模板 | 已随新指标体系同步，字段校验覆盖行级错误 | 生产按实际组织/指标清单微调 |
| 审计日志 | 已落库（登录、指标、任务、组织、角色变更） | 可接企业 SIEM |

## 八、复现命令

```bash
# 后端测试（42 项）
cd backend && pytest -q

# 前端构建校验（类型检查 + 生产打包）
cd frontend && npm run build

# 端到端冒烟（需可访问的站点；脚本见 tools/e2e-smoke.mjs）
BASE_URL=http://127.0.0.1:5173 node tools/e2e-smoke.mjs
BASE_URL=https://heyi-fleet-dashboard.app.workbuddy.host node tools/e2e-smoke.mjs
```

---

## 九、第二轮变更测试（2026-10-12）

### 9.1 后端用例（72 项，含本轮新增 30 项）

| 用例文件 | 覆盖点 | 项数 |
|---|---|---|
| `tests/test_api.py` | 鉴权、组织、角色账号、指标口径、任务 CRUD/聚合、导入导出契约 | 42 |
| `tests/test_changes.py`（**本轮扩充**） | 任务时间字段与创建人、权限可配置、周期范围、模板一致性、模板样式、解析容错 | 30 |

本轮新增/调整的关键用例：

| 用例 | 断言要点 | 结果 |
|---|---|---|
| `test_task_template_columns_match_list_and_form` | 模板列 == `TASK_COLUMNS`；不再出现「一级任务/二级任务」；含「数量单位」 | ✅ |
| `test_task_template_styling` | 首行为说明栏；表头背景 == `2E75B6` 且加粗；冻结 `A5` | ✅ |
| `test_task_template_notes_mention_unit_and_system_columns` | 说明页覆盖「数量单位」与系统列 | ✅ |
| `test_task_export_columns_align_with_list` | 导出列 == `任务ID + 12 业务列 + 5 系统列` | ✅ |
| `test_task_export_uses_dept_name_and_creator_name` | 责任部门输出**名称**而非编码；创建人输出姓名 | ✅ |
| `test_task_export_is_reimportable` | 导出文件可直接被 `parse_rows` 解析（可回灌） | ✅ |
| `test_parse_rows_skips_banner_row` | 顶部有说明栏时表头自动定位 | ✅ |
| `test_parse_rows_tolerates_legacy_template_missing_optional_column` | 老模板缺「数量单位」仍可导入，按空值处理 | ✅ |
| `test_parse_rows_still_rejects_missing_required_column` | 必填列缺失仍报错 | ✅ |
| `test_template_has_no_blank_row_after_header` | 表头下一行即示例行（回归：`freeze_panes` 曾导致空行） | ✅ |
| `test_export_has_no_blank_row_after_header` | 表头下一行即数据 | ✅ |
| `test_task_import_success`（改造） | 断言「数量单位」确实写入；创建人 == 导入操作者 | ✅ |
| `test_task_list_exposes_creator_name` | 列表返回 `createdById` / `createdByName` | ✅ |

> 用例改造说明：导入用例改为按 `TASK_COLUMNS` 构造行数据，列名或列序今后变动时用例自动跟随，避免再次出现「代码改了列、用例还在测旧列名」的漂移。

### 9.2 浏览器验收（30 项）

脚本：`tools/verify-changes.mjs`（本地与线上各跑一遍）

> **脚本等待策略（本轮修正）**：原先用固定 `waitForTimeout` 等页面渲染，在线上（跨网络）会读到上一页内容而产生**假失败**。现已改为三级等待：① 等 URL 真正切到目标路由；② 等页面特征文案；③ 任务页额外等待「任务表就绪」——驾驶舱同样有 `<table>`（6 列）而任务表是 14 列，故以**列数 ≥ 10** 作为判据。修正后本地与线上连跑三次均 30/30 稳定通过。

| 分组 | 覆盖点 | 项数 | 结果 |
|---|---|---|---|
| 1 统计周期 | 顶栏无控件、两页面内有月份组件（min/max 正确）、任务管理无、2099-12 边界不报错 | 7 | ✅ |
| 2 累计完成值 | 指标维护与驾驶舱均为「累计完成值」、旧文案已移除、项目公司列为「累计完成」 | 4 | ✅ |
| 3 任务管理 | 时间列与创建人列有值、分组视图小标题、小标题整行跨列 | 6 | ✅ |
| 4 权限可配置 | 角色表单含两个新权限项、内置标记可配置、说明文案不再写死角色 | 4 | ✅ |
| 5 本轮模板/入口 | 创建人列有值、模板与导出可下载、指标维护入口已移除且保留「查看驾驶舱」 | 9 | ✅ |

运行结果：**本地 30/30 通过、线上 30/30 通过，控制台零业务报错**。

### 9.3 模板产物校验（6 项）

以 openpyxl 直接读取生成的 `重点任务导入标准模板.xlsx` 与 `重点任务清单.xlsx`：

| 校验项 | 实际值 | 结果 |
|---|---|---|
| 说明栏标题（A1） | 模板「重点任务导入标准模板」/ 导出「重点任务清单」 | ✅ |
| 表头所在行 | 第 4 行 | ✅ |
| 表头背景 / 字色 / 加粗 | `2E75B6` / `FFFFFF` / True | ✅ |
| 冻结窗格 | `A5` | ✅ |
| 数据起始行 | 第 5 行（表头下一行，无空白行） | ✅ |
| 边框 | thin（`BDD7EE`） | ✅ |

### 9.4 本轮修复的缺陷

| 编号 | 缺陷 | 影响 | 处理 |
|---|---|---|---|
| D-1 | 导入模板缺少「数量单位」列，且 `import_tasks` 读取的键名 `单位` 在模板中并不存在 | **导入任务的单位始终为空** | 补列并修正键名，用例断言单位已写入 |
| D-2 | `_style_header` 用 `ws.cell()` 定位冻结窗格，会创建空单元格 | 模板数据整体下移一行、多出空白行 | 改为字符串 `f"A{row}"`，用例锁定 |
| D-3 | 导入接口就地硬编码列名，与 `TASK_COLUMNS` 两处维护 | 改一漏一（D-1 的根因） | 改为复用同一常量 |
| D-4 | 导出「责任部门」输出组织**编码**（如 `D01`） | 与模板填法（名称）不一致，回灌易失败 | 改输出组织名称 |

### 9.5 已知限制与后续项

- 指标维护的导入**接口**保留但前端已无入口；如需恢复，只需在 `MetricsView.vue` 重新挂上按钮（后端无需改动）。
- 导出列（18 列）多于导入模板（12 列），属刻意设计：导出为超集，可直接回灌；导入时会忽略系统列。
- 统计周期可选范围上限 2099-12 为业务约定，写在 `frontend/src/constants/period.ts`，调整只需改一处。

### 9.6 复现命令

```bash
# 后端测试（72 项）
cd backend && DATABASE_URL="sqlite:///./test.db" .venv/bin/python -m pytest -q

# 前端类型检查 + 构建
cd frontend && npm run build

# 浏览器验收（30 项；需后端可访问）
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-changes.mjs
```

---

## 十、第三轮变更测试（2026-10-12）

### 10.1 后端用例（77 项，含本轮新增 5 项）

| 用例 | 断言要点 | 结果 |
|---|---|---|
| `test_perm_catalog_exposes_project_actions` | 权限目录含 `project.create` / `project.edit` / `project.delete` | ✅ |
| `test_admin_role_includes_project_actions` | 系统管理员默认具备三个新权限点 | ✅ |
| `test_role_without_project_perm_cannot_manage_projects` | 持 `metric.edit_project` 但无项目公司权限的角色，增 / 改 / 删均 403 | ✅ |
| `test_project_manage_configurable_via_custom_role` | 新建角色勾选后即可增 / 改 / 删（与角色标识无关），且能通过可见范围校验 | ✅ |
| `test_project_delete_reassigns_dangling_refs` | 删除后子组织上移到 CO、账号迁移并停用，全库无悬空 `dept_id` / `parent_id` | ✅ |

> 本轮修复的缺陷（**D-5**）：删除项目公司后，关联账号的 `dept_id` 仍指向已被删除的组织。
> 实测确认（删 PC3 后 `U014.dept_id == 'PC3'` 且 organization 中已无 PC3）。

### 10.2 浏览器验收（54 项）

| 脚本 | 覆盖 | 项数 | 结果 |
|---|---|---|---|
| `tools/verify-round3.mjs`（**本轮新增**） | 月份组件交互（面板 / 年份跳转 / 越界禁用 / 关闭方式）、项目公司编辑删除入口 | 24 | ✅ 24/24 |
| `tools/verify-changes.mjs`（已适配新组件） | 统计周期位置与范围、累计完成值、任务管理、权限可配置、模板与入口 | 30 | ✅ 30/30 |

本轮专项要点：

| 分组 | 覆盖点 | 结果 |
|---|---|---|
| 组件交互 | 触发器格式与图标、展开面板、12 月网格、选中主色填充、范围标注 | ✅ |
| 范围约束 | 2026 年 1-8 月禁用、9-12 月可选；年份面板 2100 起禁用；2099 整年可选 | ✅ |
| 年份跳转 | 点年份标题切到年份面板，翻页可直达 2099（无需逐年点击） | ✅ |
| 关闭行为 | 选中后自动关闭并同步触发器、点击外部关闭、Esc 关闭、可还原当前周期 | ✅ |
| 项目公司入口 | 全公司视角与**项目公司视角**下删除 / 编辑入口均可见（本轮修复点） | ✅ |
| 删除确认 | 弹确认框并展示连带影响（目标 / 累计完成值 / 任务 / 账号） | ✅ |

运行结果：**本地 54/54 通过、线上 54/54 通过，控制台零错误**。

线上核对：入口产物 hash 与本地一致（`index--tnUtUiB.js`）；部署时启动脚本幂等同步内置角色，
系统管理员自动获得三个项目公司权限点（其余角色默认不授予）。

> 断言修正记录：初版脚本写「2099 年时 1-11 月禁用」是**错误假设**——上限为 `2099-12`，
> 该年 12 个月均有效；越界体现在年份面板（2100 起禁用）。已按实际语义修正断言。

### 10.3 前端构建

`vue-tsc --noEmit` 类型检查通过；`vite build` 构建成功（MonthPicker 独立分块 6.21 kB / gzip 2.52 kB）。

### 10.4 复现命令

```bash
# 后端（77 项）
cd backend && DATABASE_URL="sqlite:///./test.db" .venv/bin/python -m pytest -q

# 月份组件 + 项目公司入口专项（24 项）
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-round3.mjs

# 全量验收（30 项）
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-changes.mjs
```

---

## 十一、第四轮变更测试（2026-10-12）

### 11.1 后端用例（81 项，含本轮新增 4 项）

| 用例 | 断言要点 | 结果 |
|---|---|---|
| `test_task_status_filter_matches_computed_status` | 5 种状态逐个比对：SQL 过滤结果 == Python 计算的 `statusLevel`，且 `total` 为过滤后总数 | ✅ |
| `test_task_list_pagination_is_at_sql_level` | 单页条数受限、翻页不重不漏、页序与整体一致、越界页返回空但总数不变 | ✅ |
| `test_task_list_page_size_has_upper_bound` | `size=2000` 通过；`99999` / `0` 返回 422 | ✅ |
| `test_task_list_filters_can_combine_with_pagination` | 部门过滤 + 分页组合时，`total` 为过滤后总数而非全表总数 | ✅ |

### 11.2 浏览器验收（76 项）

| 脚本 | 覆盖 | 项数 | 结果 |
|---|---|---|---|
| `tools/verify-round4.mjs`（**本轮新增**） | 「本月」快捷项、分页、冻结列缝隙、分组标题滚动 | 22 | ✅ 22/22 |
| `tools/verify-round3.mjs` | 上一轮（月份组件交互、项目公司入口） | 24 | ✅ 24/24 |
| `tools/verify-changes.mjs` | 累计历史需求 | 30 | ✅ 30/30 |

本轮专项要点：

| 分组 | 覆盖点 | 结果 |
|---|---|---|
| 「本月」 | 面板内存在该项；从 2027年3月 一点回到 2026年10月；点击后自动关闭 | ✅ |
| 冻结列 | 滚动前后 任务ID 右边缘与 任务名称 左边缘差值 **0px**；两列 sticky 位置分别稳定在 0 / 96 | ✅ |
| 分组标题 | 横向滚动 400px 后标题仍在容器左侧 12px 处，统计数字一并固定 | ✅ |
| 平铺分页 | 标注每页 50 条；分页器显示"第 1/2 页｜共 69 条"；单页 50 行；可翻到第 2 页 | ✅ |
| 分组分页 | 每组独立分页器（"第 1/3 页 · 共 60 项"）；单组单页 ≤ 20 行；组内独立翻页到"第 2/3 页" | ✅ |

> 分页用例需造数（55 条任务），仅在**本机**执行并在结束时清理（实测删除 55/55）；
> 对线上运行时会自动跳过该段，只验证只读部分。

**线上结果**：`verify-round4` 14/14（造数场景按设计跳过，避免污染线上演示数据）、
`verify-round3` 24/24、`verify-changes` 30/30，合计 **68/68**，控制台零错误。
线上核对：入口产物 hash 与本地一致（`index-BJR1srVI.js`）；
静态资源响应头为 `content-encoding: gzip` + `cache-control: public, immutable, max-age=31536000`；
首页 `cache-control: no-cache`；`size=99999` 返回 422；指标看板 gzip 后 2236 B。

### 11.3 性能实测

| 项 | 改前 | 改后 | 变化 |
|---|---|---|---|
| 主包 JS | 169.73 KB 原样传输 | gzip 65.20 KB | **−61.6%** |
| CSS | 32.4 KB | gzip 6.5 KB | **−80%** |
| 指标看板 JSON | 13.6 KB | gzip 2.2 KB | **−83.5%** |
| 构建产物响应头 | 无 `Cache-Control` | `public, max-age=31536000, immutable` | 二次访问零请求 |
| `index.html` 响应头 | 无 | `no-cache` | 发布即时生效 |
| 任务列表查询 | 全量查出后在内存切片 | SQL `LIMIT/OFFSET` | 只读当前页 |

### 11.4 本轮修复的缺陷

| 编号 | 缺陷 | 影响 | 处理 |
|---|---|---|---|
| D-6 | `.col-id` 实际渲染宽度 87.6px，而 `.col-name` 的 sticky 偏移按 96px 计算 | 两列之间 8.4px 透明缝隙，横向滚动时透出下层内容 | 锁定 `min-width: 96px`（用例断言差值 < 1px） |
| D-7 | `.table-freeze th, td { background: #fff }` 优先级过高 | 压掉所有行级底色：分组标题的浅灰底实际渲染为纯白，hover 也失效 | 收窄为只给冻结列设背景，行底色改在 `tr` 上并让冻结列同步 |
| D-8 | 任务列表「先全量查询再内存切片」，状态过滤在 Python 层 | 分页不减少数据读取；过滤与分页分层会导致页数/总数不一致 | 分页与状态过滤一并下推 SQL（附一致性回归用例） |
| D-9 | 静态资源未压缩、无缓存头 | 169.73 KB 主包原样传输且每次访问重下 | 启用 gzip + 长期强缓存 + `index.html` no-cache |

### 11.5 复现命令

```bash
# 后端（81 项）
cd backend && DATABASE_URL="sqlite:///./test.db" .venv/bin/python -m pytest -q

# 本轮专项（22 项；本机会造数并自动清理）
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-round4.mjs

# 历史回归（24 + 30 项）
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-round3.mjs
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-changes.mjs

# 压缩与缓存头
curl -s -H "Accept-Encoding: gzip" -D - -o /dev/null http://127.0.0.1:8000/assets/index-*.js
```

---

## 十二、第五轮变更测试（2026-10-12）

### 12.1 后端用例（85 项，含本轮新增 4 项）

| 用例 | 断言要点 | 结果 |
|---|---|---|
| `test_perm_catalog_groups_metric_blocks` | 权限目录中三块分组齐全，各块下的权限 key 正确 | ✅ |
| `test_metric_edits_are_independent_per_block` | 只给「维护公司整体目标」时：能改公司目标、改监控指标被拒（提示含「监控指标」）、改项目公司被拒；只给「维护监控指标」时反之 | ✅ |
| `test_trends_batch_matches_single` | 批量接口结果与逐个调用**逐字段一致**，且保持请求顺序 | ✅ |
| `test_trends_batch_edge_cases` | 空 ids 返回空列表；不存在的指标被跳过而非报错 | ✅ |

### 12.2 浏览器验收

| 脚本 | 覆盖 | 项数 | 结果 |
|---|---|---|---|
| `tools/verify-round5.mjs`（**本轮新增**） | 权限三块分组、指标维护页渲染耗时与请求数 | 8 | ✅ 本地 8/8、线上 8/8 |
| `tools/verify-changes.mjs` | 历史需求 | 30 | ✅ 25/25（3 项空数据跳过） |
| `tools/verify-round3.mjs` | 月份组件、项目公司入口 | 24 | ✅ 24/24 |
| `tools/verify-round4.mjs` | 分页、冻结列、分组标题 | 22 | ✅ 9/9（4 项跳过） |

本轮要点：

| 检查 | 结果 |
|---|---|
| 三个分组标题展示 | ✅ 公司整体目标 / 指标监控 / 项目公司指标 |
| 各块权限归属 | ✅ 项目公司指标块含 维护 + 新增 + 编辑 + 删除 |
| 旧的笼统项已移除 | ✅ 不再出现「录入 / 修改指标」 |
| 指标维护页渲染耗时（线上） | ✅ 928 / 982 / 1121 ms（本地 257ms） |
| 趋势请求数 | ✅ 批量 1 次 / 逐个 0 次（原为 10 次） |

### 12.3 本轮修复的缺陷

| 编号 | 缺陷 | 影响 | 处理 |
|---|---|---|---|
| D-10 | `metric.edit` 是所有指标编辑的**隐含前置权限** | 勾了「维护公司整体目标」仍无法编辑，界面上看不出依赖关系 | 取消前置，三块权限各自独立；权限按块分组展示 |
| D-11 | 指标维护页为每个监控指标各发一个趋势请求且阻塞渲染 | 10 个并发互相争抢（尾请求 TTFB 2427ms），表格要等全部返回才显示 | 新增批量趋势接口（10→1），并改为不阻塞渲染 |

### 12.4 新增诊断工具

`tools/diag-metrics.mjs`：测量「点击指标维护 → 表格渲染完成」的耗时，
并按接口聚合统计请求数与 TTFB，用于定位是哪个环节在拖慢页面。

### 12.5 复现命令

```bash
# 后端（85 项）
cd backend && DATABASE_URL="sqlite:///./test.db" .venv/bin/python -m pytest -q

# 本轮专项（8 项）
cd tools && BASE_URL=https://heyi-fleet-dashboard.app.workbuddy.host node verify-round5.mjs

# 指标维护页性能诊断
cd tools && BASE_URL=https://heyi-fleet-dashboard.app.workbuddy.host node diag-metrics.mjs
```

---

## 十三、第六轮变更测试（2026-10-12）

### 13.1 后端用例（88 项，含本轮新增 3 项）

| 用例 | 断言要点 | 结果 |
|---|---|---|
| `test_org_update_returns_real_payload` | 更新接口返回的 `depth` 与各项计数与组织树中的真实值一致（原先恒为 0） | ✅ |
| `test_company_node_is_editable_but_not_deletable` | 「全公司」可改名称与负责人、`depth=0`；删除返回 409 | ✅ |
| `test_create_org_returns_real_depth` | 新建子部门的 `depth` 为父级 + 1（原先硬编码为 1） | ✅ |

### 13.2 浏览器验收（12 项）

`tools/verify-round6.mjs`（本轮新增）——本地 12/12、线上 12/12，控制台零错误：

| 检查 | 本地 | 线上 |
|---|---|---|
| 组织结构列表渲染、节点数 | ✅ 12 个 | ✅ 12 个 |
| 「全公司」出现在列表且有编辑按钮 | ✅ | ✅ |
| 「全公司」可打开编辑表单并保存 | ✅ | ✅ |
| **保存过程中不出现「加载中」** | ✅ | ✅ |
| 保存后列表条目数不变 | ✅ 12 → 12 | ✅ 12 → 12 |
| 负责人 / 名称立即更新，无需刷新 | ✅ | ✅ |
| 层级缩进保持不变 | ✅ 40px | ✅ 40px |
| 验收后数据已还原 | ✅ | ✅ |

### 13.3 本轮修复的缺陷

| 编号 | 缺陷 | 影响 | 处理 |
|---|---|---|---|
| D-12 | `saveOrg()` 保存后全量重载，且重载会切换 `orgLoading` | 每次保存列表整块闪成「加载中」，观感等同刷新页面 | 编辑就地更新；新建 / 删除静默重载 |
| D-13 | 组织创建 / 更新接口返回硬编码的 `depth` 与统计占位值 | 一旦前端就地更新，缩进层级与统计数字会立即错乱 | 新增 `_org_payload()` 返回真实数据（含回归用例） |
| D-14 | 「全公司」根节点无法编辑名称与负责人 | 公司名或负责人变更时无处维护 | 放开编辑（保留不可删除） |

> 说明：D-13 是在实施 D-12 的过程中发现的 —— 就地更新的前提是接口返回可信数据。
> 这两个缺陷有依赖关系，先补接口再改前端。

### 13.4 复现命令

```bash
# 后端（88 项）
cd backend && DATABASE_URL="sqlite:///./test.db" .venv/bin/python -m pytest -q

# 本轮专项（12 项；会改动组织数据，脚本内已还原）
cd tools && BASE_URL=https://heyi-fleet-dashboard.app.workbuddy.host node verify-round6.mjs
```

---

## 十四、第七轮变更测试（2026-10-12）

### 14.1 前端构建与类型

`vue-tsc --noEmit` 通过（确认 `orgOptions` 移除后无残留引用）；`vite build` 成功。

### 14.2 浏览器验收

| 脚本 | 覆盖 | 本地 | 线上 |
|---|---|---|---|
| `verify-changes.mjs` | 历史需求 + 新增「无组织视角下拉」等断言 | ✅ 26/26（3 跳过） | ✅ 31/31 |
| `verify-round3.mjs` | 月份组件、项目公司入口 | ✅ 23/23 | ✅ 23/23 |
| `verify-round4.mjs` | 分页、冻结列、分组标题 | ✅ 17/17（2 跳过） | ✅ 9/9（4 跳过） |
| `verify-round6.mjs` | 组织结构保存体验 | — | ✅ 12/12 |

全部零控制台错误。

### 14.3 本轮断言调整

| 脚本 | 原断言 | 调整后 |
|---|---|---|
| `verify-changes.mjs` | 切到项目公司视角 → 检查权限说明条 | 全公司范围下**不**显示部门范围说明条；文案不写死角色名 |
| `verify-round3.mjs` | 切到项目公司视角后删除 / 编辑入口仍在 | 入口按权限显示、与视角无关；并断言**顶栏无视角下拉** |
| `e2e-flow.mjs` | 「跳转不改变全局组织视角」 | 「顶栏不再提供组织视角切换」；统计周期改为读月份组件触发器 |

> 这些断言原先都依赖"切换组织视角"这个操作。功能移除后，同一意图改用
> 「不再存在该控件」+「入口与视角无关」来表达，避免断言随功能一起失效。

### 14.4 复现命令

```bash
cd tools
BASE_URL=https://heyi-fleet-dashboard.app.workbuddy.host node verify-changes.mjs
BASE_URL=https://heyi-fleet-dashboard.app.workbuddy.host node verify-round3.mjs
```

---

## 十五、第八轮变更测试（2026-10-12）

### 15.1 后端用例（92 项，含本轮新增 4 项 / 改写 3 项）

| 用例 | 断言要点 | 结果 |
|---|---|---|
| `test_dashboard_open_by_perm_not_scope` | 部门负责人在**全公司口径**下访问 summary / overview / trend / trends 均 200（不再按范围 403） | ✅ |
| `test_dashboard_task_stats_are_global` | 驾驶舱里的任务统计与管理员完全一致（全量口径） | ✅ |
| `test_task_module_still_isolates_by_scope` | 任务列表仍收窄（严格子集），范围外任务详情 403 —— 守住「唯一保留数据权限的模块」 | ✅ |
| `test_projects_list_not_scope_filtered` | 项目公司列表按全公司口径返回 | ✅ |
| `test_metric_board_open_by_perm_not_scope`（改写自 `test_head_scope_dept_sub`） | 跨组织不再 403；项目公司列全量 | ✅ |
| `test_board_project_edit_is_perm_based`（改写自 `test_board_edit_scope_dept_head_readonly`） | 有 `metric.edit_project` 即可维护全部项目公司；无权限则为空 | ✅ |
| `test_board_project_head_edit_covers_all_projects`（改写自 `test_board_project_head_only_own`） | 项目公司负责人可维护全部项目公司 | ✅ |

### 15.2 浏览器验收

| 脚本 | 覆盖 | 本地 | 线上 |
|---|---|---|---|
| `tools/verify-round7.mjs`（**本轮新增**） | 数据权限边界（驾驶舱与指标维护按权限开放、任务模块仍收窄） | ✅ 16/16 | 见下 |
| `tools/verify-changes.mjs` | 历史需求 | ✅ 26/26（3 跳过） | — |
| `tools/verify-round3.mjs` | 月份组件、项目公司入口 | ✅ 23/23 | — |
| `tools/verify-round4.mjs` | 分页、冻结列、分组标题 | ✅ 17/17（2 跳过） | — |
| `tools/verify-round5.mjs` | 权限三块分组、指标维护页性能 | ✅ 8/8 | — |
| `tools/verify-round6.mjs` | 组织结构保存体验 | ✅ 12/12 | — |

本轮专项要点：

| 分组 | 覆盖点 | 结果 |
|---|---|---|
| 驾驶舱 | 部门范围账号可见完整经营数据；无「加载失败」；「本人范围」空态已消失 | ✅ |
| 指标维护 | 三块齐全；项目公司出现 3 个（全公司口径） | ✅ |
| 任务模块 | 管理员 3 条 → 部门负责人 1 条（范围仍生效） | ✅ |
| 组织视角 | 顶栏无 `select` | ✅ |
| 数据还原 | 临时切换的可见范围已还原、造的 3 条任务已删除 | ✅ |

> `verify-round7.mjs` 需要先运行验证。脚本本身不新增账号（后端没有删除账号的 HTTP 接口），
> 而是**可逆地**临时把 `huguohai` 的可见范围切到 `dept_sub`，结束时还原并删除造的数据。

### 15.3 本轮修复的缺陷

| 编号 | 缺陷 | 影响 | 处理 |
|---|---|---|---|
| D-15 | 驾驶舱与指标维护按数据可见范围拦截与裁剪 | 部门范围账号看不到完整经营口径（403 或按部门裁剪），与「全公司与项目公司非递归汇总」的业务前提冲突 | 两模块改为只按角色权限；数据范围收敛到任务模块 |
| D-16 | 驾驶舱的任务统计沿用任务侧范围过滤 | 同一页面里指标口径为全量、任务口径为部门，结论自相矛盾 | 抽出 `dept_stats_all(db, cond=None)`，驾驶舱取全量 |
| D-17 | `build_summary` 依赖 `user` 仅为套用范围过滤 | 参数语义与模块定位不符 | 去掉该参数 |

### 15.4 复现命令

```bash
# 后端（92 项）
cd backend && DATABASE_URL="sqlite:///./test.db" .venv/bin/python -m pytest -q

# 本轮专项（16 项；会临时改可见范围与造数，脚本内已还原）
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-round7.mjs
```

---

## 十六、第九轮变更测试（2026-10-13）

### 16.1 后端用例（92 项）

无新增用例（本轮为前端视觉与文案清理）。全量回归 **92 passed**。

> 旧叫法清理涉及后端 `schemas/task.py` 的描述字段与 `importer.py` 注释，
> 已有用例 `test_task_template_columns_match_list_and_form` 覆盖模板列名一致性 ✅

### 16.2 浏览器验收（119 项全绿）

| 脚本 | 覆盖 | 结果 |
|---|---|---|
| `tools/verify-round8.mjs`（**本轮新增**） | 视觉体系落地与一致性 | ✅ 17/17 |
| `tools/verify-changes.mjs` | 历史需求 | ✅ 26/26（3 跳过） |
| `tools/verify-round3.mjs` | 月份组件、项目公司入口 | ✅ 23/23 |
| `tools/verify-round4.mjs` | 分页、冻结列、分组标题 | ✅ 17/17（2 跳过） |
| `tools/verify-round5.mjs` | 权限三块分组、指标维护页性能 | ✅ 8/8 |
| `tools/verify-round6.mjs` | 组织结构保存体验 | ✅ 12/12 |
| `tools/verify-round7.mjs` | 数据权限边界 | ✅ 16/16 |
| `tools/verify-no-external-font.mjs` | 零外部请求与零外部字体 | ✅ 通过 |

本轮视觉专项要点：

| 检查 | 结果 |
|---|---|
| 登录页新渐变（单色相 Electric Blue） | ✅ |
| 区块标识（pill + 脉冲点） | ✅ 动画名 `pulseDot` 生效 |
| 侧边栏选中项新渐变 | ✅ |
| 旧靛蓝/紫色（`#4F46E5` / `#7C3AED`）残留 | ✅ 0 处 |
| 主按钮 12px 圆角 + 品牌色阴影 | ✅ 三个页面均通过 |
| 卡片 16px 圆角 + 品牌色阴影 | ✅ 四个页面均通过 |
| 区块标题特粗（800）+ `-0.28px` 字距 | ✅ |
| 零外部请求 / 零外部字体 | ✅ |
| 控制台错误 | ✅ 0 个 |

### 16.3 本轮的过程记录（两处断言自身的错误）

| 现象 | 原因 | 修正 |
|---|---|---|
| 阴影断言全部失败，读出 `rgba(0,0,0,0) 0px 0px 0px 0px, ...` | `box-shadow` 由三个 CSS 变量拼接（前两段是透明的 ring 占位），真实阴影在第三段，我的 `.slice(0, 46)` 把它截掉了 | 读完整字符串再判断 |
| 字距断言失败（实测 `-0.28px`，断言写 `-0.32px`） | `.section-title` 是 `text-sm`（14px），`-0.02em × 14px = -0.28px`；我按 16px 计算 | 按实际字号修正 |

> 两次都是**断言写错而非实现有问题**。构建产物核对确认样式正确
> （`.card{--tw-shadow: 0 4px 20px -2px rgba(0, 82, 255, .1); ...}`）。

### 16.4 复现命令

```bash
# 后端（92 项）
cd backend && DATABASE_URL="sqlite:///./test.db" .venv/bin/python -m pytest -q

# 视觉专项（17 项，含截图输出到 /tmp/ui-shots）
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-round8.mjs

# 零外部字体硬约束
cd tools && BASE_URL=http://127.0.0.1:8000 node verify-no-external-font.mjs
```

### 16.5 线上验证（2026-10-13）

| 脚本 | 结果 |
|---|---|
| `verify-round8.mjs`（视觉专项） | ✅ 17/17 |
| `verify-round7.mjs`（数据权限边界） | ✅ 16/16（修正认证方式后） |
| `verify-changes.mjs` | ✅ 31/31 |
| `verify-round3.mjs` | ✅ 23/23 |
| `verify-round4.mjs` | ✅ 9/9（4 项跳过） |
| `verify-round5.mjs` | ✅ 8/8 |
| `verify-round6.mjs` | ✅ 12/12 |
| `verify-no-external-font.mjs` | ✅ 通过 |

线上核对：产物 hash 与本地一致；CSS 含新主色 `#0052FF`/`#4D7CFF`，**旧靛蓝/紫色 0 残留**；
数据无污染（验收脚本造的 3 条任务已删除、临时切换的可见范围已还原）。

> 线上同时也验证了第八批的数据权限口径 —— 部门范围账号在驾驶舱与指标维护可见全公司数据，
> 而在任务管理仍只见范围内数据（管理员 4 条 → 部门负责人 1 条）。
>
> **过程记录**：`verify-round7` 首次在线上跑时 3 项失败，根因是脚本用 `fetch + Bearer` 做管理端调用，
> 而线上网关会覆盖 `Authorization` 头（本地无网关所以没暴露）。改用独立浏览器上下文的 Cookie 后通过。
> 这条已写入 `交接说明.md` 的坑列表。
