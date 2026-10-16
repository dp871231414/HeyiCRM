import { http } from './http'
import type {
  AccountRefs,
  DeptTaskFilter,
  DeptTaskStat,
  FunnelProbItem,
  ImportResult,
  LoginResult,
  MainTask,
  MarketOwner,
  MarketProjectItem,
  MeResult,
  MetricBoard,
  OrgNode,
  OverviewResult,
  PermCatalog,
  ProjectFunnelResult,
  ProjectItem,
  RoleItem,
  SummaryResult,
  TaskItem,
  TaskProgressItem,
  TaskProgressListOut,
  TrendResult,
  UserItem,
} from '@/types'

/* ---------------- 元数据 ---------------- */
export const metaApi = {
  orgs: () =>
    http.get<{ id: string; name: string; type: string; parentId: string | null; head: string; depth: number }[]>('/meta/orgs').then(
      (r) => r.data,
    ),
  owners: () => http.get<{ id: string; name: string; deptId: string }[]>('/meta/owners').then((r) => r.data),
  marketOwners: () => http.get<MarketOwner[]>('/meta/market-owners').then((r) => r.data),
}

/* ---------------- 鉴权 ---------------- */
export const authApi = {
  login: (account: string, password: string) =>
    http.post<LoginResult>('/auth/login', { account, password }).then((r) => r.data),
  logout: () => http.post('/auth/logout').then((r) => r.data),
  me: () => http.get<MeResult>('/auth/me').then((r) => r.data),
}

/* ---------------- 用户偏好（按账号记忆） ---------------- */
export const prefsApi = {
  get: () => http.get<{ preferences: Record<string, unknown> }>('/auth/preferences').then((r) => r.data),
  update: (preferences: Record<string, unknown>) =>
    http.put<{ preferences: Record<string, unknown> }>('/auth/preferences', { preferences }).then((r) => r.data),
}

/* ---------------- 组织 ---------------- */
export const orgApi = {
  list: (flat = 1) => http.get<OrgNode[]>('/orgs', { params: { flat } }).then((r) => r.data),
  create: (payload: { name: string; parent_id: string; head?: string }) =>
    http.post<OrgNode>('/orgs', payload).then((r) => r.data),
  update: (id: string, payload: { name: string; head?: string }) =>
    http.patch<OrgNode>(`/orgs/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete(`/orgs/${id}`).then((r) => r.data),
  impact: (id: string) => http.get(`/orgs/${id}/impact`).then((r) => r.data),
}

/* ---------------- 项目公司 ---------------- */
export const projectApi = {
  list: () => http.get<ProjectItem[]>('/projects').then((r) => r.data),
  create: (payload: { name: string; head?: string; targets?: { metric_id: string; value: number; year: string }[] }) =>
    http.post('/projects', payload).then((r) => r.data),
  update: (id: string, payload: { name: string; head?: string }) =>
    http.patch(`/projects/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete(`/projects/${id}`).then((r) => r.data),
  impact: (id: string) => http.get(`/projects/${id}/impact`).then((r) => r.data),
}

/* ---------------- 角色与账号 ---------------- */
export const roleApi = {
  catalog: () => http.get<PermCatalog>('/permissions').then((r) => r.data),
  list: (keyword = '') => http.get<RoleItem[]>('/roles', { params: { keyword } }).then((r) => r.data),
  create: (payload: Partial<RoleItem>) => http.post<RoleItem>('/roles', payload).then((r) => r.data),
  update: (id: string, payload: Partial<RoleItem>) => http.patch<RoleItem>(`/roles/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete(`/roles/${id}`).then((r) => r.data),
}

export const userApi = {
  list: (params: { keyword?: string; dept_id?: string; status?: string } = {}) =>
    http.get<UserItem[]>('/users', { params }).then((r) => r.data),
  create: (payload: Record<string, unknown>) => http.post<UserItem>('/users', payload).then((r) => r.data),
  update: (id: string, payload: Record<string, unknown>) => http.patch<UserItem>(`/users/${id}`, payload).then((r) => r.data),
  setStatus: (id: string, status: string) => http.post<UserItem>(`/users/${id}/status`, { status }).then((r) => r.data),
  remove: (id: string) => http.delete(`/users/${id}`).then((r) => r.data),
  impact: (id: string) => http.get<AccountRefs>(`/users/${id}/impact`).then((r) => r.data),
  importFile: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post<ImportResult>('/users/import', fd).then((r) => r.data)
  },
  templateUrl: () => '/api/v1/users/import/template',
}

/* ---------------- 指标 ---------------- */
export const metricApi = {
  board: (period: string, orgId: string) =>
    http.get<MetricBoard>('/metrics/board', { params: { period, org_id: orgId } }).then((r) => r.data),
  periods: () => http.get<{ current: string; dataAsOf: string; periods: string[] }>('/metrics/periods').then((r) => r.data),
  defs: (group = '') => http.get('/metrics/defs', { params: { group } }).then((r) => r.data),
  saveTarget: (payload: { metric_id: string; org_id: string; period: string; value: number | null }) =>
    http.put('/metrics/targets', payload).then((r) => r.data),
  saveActual: (payload: { metric_id: string; org_id: string; period: string; value: number | null }) =>
    http.put('/metrics/actuals', payload).then((r) => r.data),
  importFile: (file: File, period: string) => {
    const fd = new FormData()
    fd.append('file', file)
    return http
      .post<ImportResult>('/metrics/import', fd, { params: { period } })
      .then((r) => r.data)
  },
  templateUrl: () => '/api/v1/metrics/import/template',
}

/* ---------------- 主任务（原任务分类） ---------------- */
export const mainTaskApi = {
  list: () => http.get<MainTask[]>('/main-tasks').then((r) => r.data),
  create: (name: string) => http.post<MainTask>('/main-tasks', { name }).then((r) => r.data),
  rename: (id: string, name: string) => http.patch<MainTask>(`/main-tasks/${id}`, { name }).then((r) => r.data),
}

/* ---------------- 任务 ---------------- */
export const taskApi = {
  list: (params: { keyword?: string; dept_id?: string; status?: string; page?: number; size?: number } = {}) =>
    http.get<{ items: TaskItem[]; total: number; page: number; size: number }>('/tasks', { params }).then((r) => r.data),
  detail: (id: string) => http.get<TaskItem>(`/tasks/${id}`).then((r) => r.data),
  create: (payload: Record<string, unknown>) => http.post<TaskItem>('/tasks', payload).then((r) => r.data),
  update: (id: string, payload: Record<string, unknown>) => http.patch<TaskItem>(`/tasks/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete(`/tasks/${id}`).then((r) => r.data),
  /** 进展记录：倒序分页（默认最近 5 条，下拉加载更早） */
  progressList: (id: string, params: { page?: number; size?: number } = {}) =>
    http.get<TaskProgressListOut>(`/tasks/${id}/progress`, { params }).then((r) => r.data),
  /** 追加一条进展记录（编辑界面不可直接改进展描述，只能追加） */
  progressAdd: (id: string, content: string) =>
    http.post<TaskProgressItem>(`/tasks/${id}/progress`, { content }).then((r) => r.data),
  deptStats: () => http.get<DeptTaskStat[]>('/tasks/dept-stats').then((r) => r.data),
  importFile: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post<ImportResult>('/tasks/import', fd).then((r) => r.data)
  },
  templateUrl: () => '/api/v1/tasks/import/template',
  exportUrl: () => '/api/v1/tasks/export',
}

/* ---------------- 项目管理（市场项目/商机） ---------------- */
export const marketApi = {
  list: (params: { keyword?: string; stage?: number | ''; page?: number; size?: number } = {}) =>
    http
      .get<{ items: MarketProjectItem[]; total: number; page: number; size: number }>('/market-projects', {
        // stage 为空串时必须丢掉：后端是 int 参数，空串会被 422 拒绝
        params: { ...params, stage: params.stage === '' ? undefined : params.stage },
      })
      .then((r) => r.data),
  create: (payload: Record<string, unknown>) =>
    http.post<MarketProjectItem>('/market-projects', payload).then((r) => r.data),
  update: (id: string, payload: Record<string, unknown>) =>
    http.patch<MarketProjectItem>(`/market-projects/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete(`/market-projects/${id}`).then((r) => r.data),
  /** 按市场部人员清单重新生成项目数据（删除全部后逐个重建） */
  reseed: () => http.post<{ ok: boolean; msg: string; created: number }>('/market-projects/reseed').then((r) => r.data),
}

/* ---------------- 驾驶舱 ---------------- */
export const dashboardApi = {
  summary: (period: string, orgId: string) =>
    http.get<SummaryResult>('/dashboard/summary', { params: { period, org_id: orgId } }).then((r) => r.data),
  overview: (period: string, orgId: string) =>
    http.get<OverviewResult>('/dashboard/overview', { params: { period, org_id: orgId } }).then((r) => r.data),
  /** 部门任务完成度：切换筛选只重算一次聚合，故独立于总览单独取数 */
  deptTaskStats: (period: string, filter: DeptTaskFilter) =>
    http.get<DeptTaskStat[]>('/dashboard/dept-task-stats', { params: { period, filter } }).then((r) => r.data),
  trend: (metricId: string, orgId: string) =>
    http.get<TrendResult>(`/dashboard/metrics/${metricId}/trend`, { params: { org_id: orgId } }).then((r) => r.data),
  /** 批量取趋势：一次请求代替 N 次（避免并发争抢把尾请求拖慢） */
  trends: (metricIds: string[], orgId: string) =>
    http
      .get<{ series: TrendResult[] }>('/dashboard/metrics/trends', {
        params: { ids: metricIds.join(','), org_id: orgId },
      })
      .then((r) => r.data),
  /** 市场项目概览：三漏斗 + 加权销量预测（只按角色权限，不看数据范围）
   *  dept 为二级部门 ID 时只统计该部门负责人的项目；为空（全部）统计市场部子树全部负责人。 */
  projectFunnel: (dept?: string) =>
    http
      .get<ProjectFunnelResult>('/dashboard/project-funnel', { params: dept ? { dept } : {} })
      .then((r) => r.data),
  funnelConfig: () =>
    http.get<{ probs: FunnelProbItem[] }>('/dashboard/funnel-config').then((r) => r.data),
  saveFunnelConfig: (probs: FunnelProbItem[]) =>
    http.put<{ probs: FunnelProbItem[] }>('/dashboard/funnel-config', { probs }).then((r) => r.data),
}

/** 带令牌下载文件（模板/导出） */
export async function downloadFile(url: string, filename: string) {
  const token = localStorage.getItem('fleet_token')
  const resp = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {}, credentials: 'include' })
  if (!resp.ok) throw new Error('下载失败')
  const blob = await resp.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}
