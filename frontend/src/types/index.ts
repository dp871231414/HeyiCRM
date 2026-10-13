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
  description: string
  abnormal: boolean
  target: number
  done: number
  unit: string
  note: string
  startDate: string
  endDate: string
  deptId: string
  deptName: string
  owner: string
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
  deptTaskStats: DeptTaskStat[]
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
