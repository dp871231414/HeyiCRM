/** 与后端 schema 对齐的类型定义（见 design.md §6） */

export type Light = 'green' | 'amber' | 'red' | 'none'

/**
 * 单个指标的进度状态 —— 全系统统一口径，由服务端按「达成率 ÷ 时间进度」判定。
 * done=已完成（达成率 ≥ 100%）/ ahead=领先 / near=偏慢 / risk=滞后 / none=未录入
 *
 * 与 `Light` 的区别：Light 是「实际 vs 目标」的达成判定（含 warn/danger 阈值，年中看
 * 年度目标恒为未达标），仅用于回款率等子指标；界面上的指标状态一律用 PerfTone。
 */
export type PerfTone = 'done' | 'ahead' | 'near' | 'risk' | 'none'

/** 汇总统计：与卡片标签同源，按 PerfTone 分档 */
export interface ToneCounts {
  total: number
  done: number
  ahead: number
  near: number
  risk: number
  none: number
  filled: number
}
export type ScopeKey = 'self' | 'dept' | 'dept_sub' | 'all'

export interface UserBrief {
  id: string
  name: string
  account: string
  deptId: string
  deptName: string
  roleId: string
  roleName: string
  scope: ScopeKey
  status: string
  /** 用户级偏好（行高、视图等），按账号记忆、下次登录仍生效 */
  preferences?: Record<string, unknown>
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: UserBrief
  perms: string[]
}

export interface MeResult {
  user: UserBrief
  perms: string[]
  visibleOrgs: string[]
}

export interface OrgNode {
  id: string
  name: string
  type: 'company' | 'dept' | 'team' | 'project'
  parentId: string | null
  head: string
  depth: number
  userCount: number
  childCount: number
  taskCount: number
}

export interface Impact {
  users: number
  children: number
  tasks: number
  targets: number
  actuals: number
}

export interface ProjectItem {
  id: string
  name: string
  head: string
  parentId: string | null
  impact: Impact
}

export interface RoleItem {
  id: string
  name: string
  description: string
  scope: ScopeKey
  scopeLabel: string
  isSystem: boolean
  permissions: string[]
  userCount: number
}

export interface UserItem {
  id: string
  name: string
  account: string
  deptId: string
  deptName: string
  roleId: string
  roleName: string
  scope: ScopeKey | null
  effectiveScope: string
  status: string
  lastLoginAt: string | null
  lastLoginIp: string | null
}

/** 账号被引用的情况 · 用于删除前预检（任一计数 > 0 即不允许删除） */
export interface AccountRefs {
  taskCreated: number
  projectCreated: number
  metricCreated: number
  taskOwner: number
  projectOwner: number
  orgHead: number
  self: boolean
}

export interface PermItem {
  key: string
  label: string
  type: 'menu' | 'action'
  /** 可选的子分组名：用于把权限按「页面上的哪一块」归类显示（如 公司整体目标 / 指标监控） */
  group?: string
}
export interface PermGroup {
  menu: string
  label: string
  items: PermItem[]
}
export interface PermCatalog {
  groups: PermGroup[]
  scopes: { value: ScopeKey; label: string }[]
}

export interface MetricRow {
  metricId: string
  name: string
  unit: string
  group: string
  family: string
  direction: 'positive' | 'negative'
  weight: number
  snapshot: boolean
  noTarget: boolean
  ownerOrgId: string | null
  ownerOrgName: string
  description: string
  target: number | null
  actual: number | null
  rate: number | null
  rateText: string
  light: Light
  /** 进度状态（界面统一用这个，不用 light） */
  tone: PerfTone
  gap: number | null
  hasCollection: boolean
  collMetricId: string | null
  collActual: number | null
  collRate: number | null
  collLight: Light
  vsTime: number | null
  periodLabel: string
}

export interface ProjectCompanyBlock {
  orgId: string
  name: string
  head: string
  cells: MetricRow[]
  completion: number | null
  /** 完成率的进度状态（与单元格徽章同一套判档） */
  completionTone: PerfTone
  filled: number
  total: number
}

export interface MetricBoard {
  period: string
  currentPeriod: string
  dataAsOf: string
  timeProgress: number
  orgId: string
  /** 当前视角组织类型 · 用于部门/班组视角的空态说明 */
  orgType: string
  annual: MetricRow[]
  monitor: MetricRow[]
  project: { companies: ProjectCompanyBlock[]; metrics: { id: string; name: string; unit: string; snapshot: boolean }[] }
  counts: ToneCounts
  /** 能否编辑「公司整体目标」（需 metric.edit_company，且当前视角为公司） */
  canEditAll?: boolean
  /** 能否编辑「指标监控」（需 metric.edit） */
  canEditMonitor?: boolean
  editableProjects?: string[]
  /** 当前账号的指标维护权限（后端按权限返回，与角色属性无关） */
  perms?: { edit: boolean; editCompany: boolean; editProject: boolean }
}

export interface TaskItem {
  id: string
  parent: string
  title: string | null
  /** 主任务（原「任务分类」）：下拉选择，单独建表 */
  mainTaskId: string
  mainTaskName: string
  description: string
  abnormal: boolean
  target: number
  done: number
  unit: string
  note: string
  /** 最新一条进展记录内容（列表「进展描述」列展示用） */
  latestProgress: string
  startDate: string
  endDate: string
  deptId: string
  deptName: string
  owner: string
  ownerId: string
  progress: number
  daysLeft: number | null
  statusLevel: 'done' | 'overdue' | 'due_soon' | 'normal' | 'risk'
  statusLabel: string
  /** 系统自动记录，只读 */
  createdById: string
  createdByName: string
  createdAt: string
  updatedAt: string
}

/** 主任务（下拉选项）。系统默认「空」始终存在，任务未选主任务时默认关联它。
 * 责任人/责任部门在主任务首次被任务选用时由该任务回填（ownerId/ownerName/deptId/deptName）。 */
export interface MainTask {
  id: string
  name: string
  createdAt: string
  createdBy: string
  createdByName: string
  /** 责任人（主任务首次被任务选用时回填） */
  ownerId: string
  ownerName: string
  /** 责任部门 */
  deptId: string
  deptName: string
  updatedAt: string
  isSystem: boolean
}

export interface DeptTaskStat {
  deptId: string
  deptName: string
  total: number
  done: number
  overdue: number
  risk: number
  dueSoon: number
  completion: number
}

/** 任务进展记录（时间轴，倒序分页） */
export interface TaskProgressItem {
  id: number
  content: string
  createdById: string
  createdByName: string
  createdAt: string
}
export interface TaskProgressListOut {
  items: TaskProgressItem[]
  total: number
  page: number
  size: number
}

export interface SummaryResult {
  headline: string
  /** 整体经营结论（与单指标的 PerfTone 不是同一概念） */
  verdict: 'good' | 'warn' | 'bad' | 'none'
  weighted: number | null
  timeProgress: number
  vsTime: number | null
  counts: ToneCounts
  points: string[]
  risks: { type: string; org: string; text: string }[]
  wins: string[]
}

export interface OverviewResult {
  period: string
  orgId: string
  orgName: string
  orgType: string
  timeProgress: number
  annual: MetricRow[]
  monitor: MetricRow[]
  projectCompare: ProjectCompanyBlock[]
  projectMetrics: { id: string; name: string; unit: string; snapshot: boolean }[]
  counts: ToneCounts
}

/** 部门任务完成度的展示口径筛选：全部 / 本年新增 / 当月新增（取页面顶部月份）/ 未结束 */
export type DeptTaskFilter = 'all' | 'year' | 'month' | 'open'

/* ---------------- 项目管理（市场项目） ---------------- */

/** 项目阶段即漏斗层级：10 项目导入 / 25 市场尽调 / 50 初审通过 / 75 联合评审通过 / 90 签约落地 / 100 交车投运 */
export type MarketStage = 10 | 25 | 50 | 75 | 90 | 100

export interface MarketProjectItem {
  id: string
  name: string
  description: string
  /** 最新一条进展的冗余快照（列表「项目进展」列展示用） */
  latestProgress: string
  tractorDemand: number
  trailerDemand: number
  stage: MarketStage
  stageLabel: string
  owner: string
  ownerDeptId: string
  ownerDeptName: string
  createdById: string
  createdByName: string
  createdAt: string
  updatedAt: string
}

/** 项目进展记录（时间轴，倒序分页） */
export interface ProjectProgressItem {
  id: number
  content: string
  createdById: string
  createdByName: string
  createdAt: string
}
export interface ProjectProgressListOut {
  items: ProjectProgressItem[]
  total: number
  page: number
  size: number
}

/** 市场部人员（项目管理负责人候选） */
export interface MarketOwner {
  id: string
  name: string
  deptId: string
  deptName: string
}

export interface FunnelStageStat {
  stage: MarketStage
  label: string
  /** 该阶段的转化概率（0~1），默认与阶段百分比一致 */
  prob: number
  /** 当前阶段口径：仅 stage == 该层的项目数（不向上累计） */
  count: number
  /** 当前阶段口径：stage == 该层的牵引车需求数 */
  tractor: number
  /** 当前阶段口径：stage == 该层的挂车需求数 */
  trailer: number
}

export interface ProjectFunnelResult {
  stages: FunnelStageStat[]
  forecast: { tractor: number; trailer: number }
  /** 市场部直接子部门（二级部门）列表，供「市场项目概览」筛选标签渲染 */
  deptOptions: { id: string; name: string }[]
}

export interface FunnelProbItem {
  stage: MarketStage
  prob: number
}

export const MARKET_STAGE_LABELS: Record<number, string> = {
  10: '项目导入',
  25: '市场尽调',
  50: '初审通过',
  75: '联合评审通过',
  90: '签约落地',
  100: '交车/投运',
}

export interface ImportError {
  row: number
  field: string
  msg: string
}
export interface ImportResult {
  imported: number
  errors: ImportError[]
}

export interface TrendResult {
  metricId: string
  name: string
  unit: string
  direction: string
  points: { period: string; value: number }[]
}

export interface ApiError {
  detail: string
  code?: string
}
