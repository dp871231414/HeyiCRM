/** 与后端 schema 对齐的类型定义（见 design.md §6） */

export type Light = 'green' | 'amber' | 'red' | 'none'
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
  counts: { total: number; green: number; amber: number; red: number; none: number; filled: number }
  canEditAll?: boolean
  editableProjects?: string[]
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
  tone: 'good' | 'warn' | 'bad'
  weighted: number | null
  timeProgress: number
  vsTime: number | null
  counts: { total: number; green: number; amber: number; red: number; none: number; filled: number }
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
  counts: { total: number; green: number; amber: number; red: number; none: number; filled: number }
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
