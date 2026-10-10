# 合一重卡生态经营看板 · 任务清单（tasks）

> 排序原则：基础设施 → 核心功能 → 界面 → 部署与验收
> 每个任务完成后对照「完成标准」自检、验收并单独提交（`feat: complete T<n> <任务名>`）。

## T1 工程骨架与配置
- 优先级：P0
- 前置依赖：无
- 涉及文件/模块：`backend/app/{config,main}.py`、`backend/app/db/{base,session}.py`、`backend/requirements.txt`、`frontend/{package.json,vite.config.ts,tailwind.config.js,tsconfig.json,index.html}`、`deploy/.env.example`
- 具体工作内容：搭建后端 FastAPI 目录骨架与配置模块（环境变量外置）；搭建前端 Vite + TS + Tailwind 工程骨架；编写依赖清单
- 完成标准：后端 `python -c "import app.main"` 通过；前端 `npm install && npm run build` 通过
- 验证方式：`uvicorn app.main:app --help` 与 `npm run build`
- 是否可并行：否

## T2 数据模型与迁移
- 优先级：P0
- 前置依赖：T1
- 涉及文件/模块：`backend/app/models/*`、`backend/app/db/base.py`、`backend/alembic/*`
- 具体工作内容：实现 organization / metric_def / metric_target / metric_actual / task / user / role / operation_log 八张表的 ORM；配置 Alembic 并生成初始迁移
- 完成标准：`alembic upgrade head` 建表成功；`alembic downgrade base` 可回滚
- 验证方式：迁移命令 + 表结构核对
- 是否可并行：否

## T3 种子数据
- 优先级：P0
- 前置依赖：T2
- 涉及文件/模块：`backend/app/seed.py`
- 具体工作内容：写入全公司 + 11 个二级部门 + 3 家项目公司、24 项指标定义、年度/项目公司目标、演示账号（管理员/部门负责人/成员/项目公司负责人）、3 个内置角色
- 完成标准：执行脚本后各表有数据；`seed --reset` 可重复执行
- 验证方式：查询各表行数
- 是否可并行：是（与 T4 无文件冲突）

## T4 鉴权与权限依赖
- 优先级：P0
- 前置依赖：T2, T3
- 涉及文件/模块：`backend/app/core/{security,deps}.py`、`backend/app/api/v1/auth.py`
- 具体工作内容：bcrypt 密码哈希；JWT 签发/校验；`get_current_user`、`require_perm`、`require_any_perm` 依赖；登录/登出/me 接口；登录写 operation_log（含 IP）
- 完成标准：正确凭据返回令牌；错误凭据 401；无权限访问受保护接口 403
- 验证方式：pytest + curl
- 是否可并行：否

## T5 组织与项目公司 API
- 优先级：P0
- 前置依赖：T4
- 涉及文件/模块：`backend/app/api/v1/{orgs,projects}.py`、`backend/app/schemas/org.py`
- 具体工作内容：组织树/扁平列表、部门增改删（含删除约束）、影响面；项目公司列表/新增/编辑/删除（连带清理与账号停用）
- 完成标准：重名 409；有账号的部门删除 409；删除项目公司后其目标/完成值/任务被清理
- 验证方式：pytest
- 是否可并行：是

## T6 角色与账号 API
- 优先级：P0
- 前置依赖：T4
- 涉及文件/模块：`backend/app/api/v1/{roles,users}.py`、`backend/app/schemas/{role,user}.py`
- 具体工作内容：权限清单接口；角色增删改（内置/占用约束）；账号增删改查、启停用、可见范围覆盖
- 完成标准：内置角色删除 409；角色下有账号删除 409；账号 scope 留空则跟随角色
- 验证方式：pytest
- 是否可并行：是（与 T5 无文件冲突）

## T7 指标计算与范围服务
- 优先级：P0
- 前置依赖：T2
- 涉及文件/模块：`backend/app/services/{achievement,scope}.py`
- 具体工作内容：达成率（正向/逆向/零目标）、红黄绿灯、回款率与回款灯、时间进度、加权；可见组织集合、可见任务过滤
- 完成标准：单元测试覆盖三类指标判定与四类范围
- 验证方式：pytest
- 是否可并行：是

## T8 指标 API 与维护看板数据
- 优先级：P0
- 前置依赖：T5, T7
- 涉及文件/模块：`backend/app/api/v1/metrics.py`、`backend/app/schemas/metric.py`
- 具体工作内容：指标定义、周期、维护看板一次性数据（三模块）、目标/完成值 upsert（年度目标换算年份周期）、权限与范围校验
- 完成标准：维护看板返回三模块且口径与驾驶舱一致；越权 org_id 返回 403
- 验证方式：pytest + curl
- 是否可并行：否

## T9 任务 API 与部门聚合
- 优先级：P0
- 前置依赖：T5, T7
- 涉及文件/模块：`backend/app/api/v1/tasks.py`、`backend/app/schemas/task.py`
- 具体工作内容：任务增删改查（服务端范围过滤）、部门任务完成度聚合（SQL GROUP BY）、筛选与分页
- 完成标准：成员仅见本人相关任务；部门聚合与逐条计算一致
- 验证方式：pytest
- 是否可并行：否

## T10 分析总结服务与驾驶舱 API
- 优先级：P0
- 前置依赖：T7, T8, T9
- 涉及文件/模块：`backend/app/services/summary.py`、`backend/app/api/v1/dashboard.py`
- 具体工作内容：规则生成分析总结（结论/亮点/风险/建议）；驾驶舱总览（核心指标/项目公司对比/监控/部门任务）；指标趋势
- 完成标准：无 AI 依赖；空数据返回空态不报错；汇总在 SQL 层完成
- 验证方式：pytest
- 是否可并行：否

## T11 Excel 导入与导出
- 优先级：P1
- 前置依赖：T8, T9
- 涉及文件/模块：`backend/app/services/importer.py`、`backend/app/api/v1/{tasks,metrics}.py`
- 具体工作内容：任务模板（11 列）与指标模板生成下载；逐行校验（任务 8 类）；原子导入；任务导出
- 完成标准：含错误行时返回错误明细且不写入脏数据；合法行正确入库
- 验证方式：pytest + 真实上传演示
- 是否可并行：是

## T12 前端骨架与外壳
- 优先级：P0
- 前置依赖：T1
- 涉及文件/模块：`frontend/src/{main.ts,App.vue}`、`router/`、`stores/`、`api/`、`layouts/`、`styles/`
- 具体工作内容：路由与权限守卫、Pinia 状态、Axios 封装（令牌与 401/403 拦截）、侧边栏+顶栏外壳、设计令牌与 Tailwind 主题
- 完成标准：登录后进入外壳；未登录访问业务路由跳登录；无权限菜单不渲染
- 验证方式：`npm run build` + 浏览器手工
- 是否可并行：否

## T13 登录页
- 优先级：P0
- 前置依赖：T4, T12
- 涉及文件/模块：`frontend/src/views/LoginView.vue`
- 具体工作内容：品牌视觉区（含科技感装饰）、登录表单、错误提示；未登录不请求任何业务数据
- 完成标准：正确凭据进入系统；错误提示不泄露账号存在性
- 验证方式：浏览器手工 + 组件测试
- 是否可并行：是

## T14 经营驾驶舱页
- 优先级：P0
- 前置依赖：T10, T12
- 涉及文件/模块：`frontend/src/views/DashboardView.vue`、相关组件
- 具体工作内容：分析总结区、核心指标卡（含回款与时间进度）、项目公司对比、监控区、部门任务完成度、风险清单（置文末）
- 完成标准：各区块渲染无 NaN/undefined；空态正确；点「去维护」定位到指标页
- 验证方式：浏览器手工 + 截图
- 是否可并行：是

## T15 任务管理页
- 优先级：P0
- 前置依赖：T9, T11, T12
- 涉及文件/模块：`frontend/src/views/TasksView.vue`、组件
- 具体工作内容：任务表（冻结列/横滑）、搜索筛选、增删改、导入导出、弹窗表单
- 完成标准：完成进度与状态由服务端计算且展示正确；按钮按权限显隐
- 验证方式：浏览器手工
- 是否可并行：是

## T16 指标维护页
- 优先级：P0
- 前置依赖：T8, T11, T12
- 涉及文件/模块：`frontend/src/views/MetricsView.vue`、组件
- 具体工作内容：三模块布局、行内录入与保存、项目公司列表化增删、导入、与驾驶舱互跳定位
- 完成标准：保存后驾驶舱同步；未录入显示「—」；项目公司增删生效
- 验证方式：浏览器手工
- 是否可并行：是

## T17 账号管理页（账号/组织/角色）
- 优先级：P0
- 前置依赖：T5, T6, T12
- 涉及文件/模块：`frontend/src/views/AccountsView.vue`、组件
- 具体工作内容：账号页签、组织结构页签（部门 CRUD）、角色权限页签（勾选树 + 可见范围）
- 完成标准：删除约束正确提示；菜单权限取消联动按钮权限；组织页无项目公司入口
- 验证方式：浏览器手工
- 是否可并行：是

## T18 部署编排与文档
- 优先级：P0
- 前置依赖：T12 ~ T17
- 涉及文件/模块：`deploy/docker-compose.yml`、`deploy/nginx.conf`、`backend/Dockerfile`、`frontend/Dockerfile`、`README.md`
- 具体工作内容：一键启动数据库/后端/前端/Nginx；环境变量外置；部署手册
- 完成标准：`docker compose up` 后浏览器可访问并登录
- 验证方式：本地 compose 启动核对
- 是否可并行：否

## T19 端到端验收与回归
- 优先级：P0
- 前置依赖：T1 ~ T18
- 涉及文件/模块：`backend/tests/`、验收记录
- 具体工作内容：逐条执行 proposal §11 验收标准；修复发现的问题
- 完成标准：AC-01 ~ AC-39 全部通过
- 验证方式：pytest + 浏览器手工逐条核对
- 是否可并行：否
