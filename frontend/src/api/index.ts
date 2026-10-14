import { http } from './http'
import type {
  DeptTaskFilter,
  DeptTaskStat,
  ImportResult,
  LoginResult,
  MeResult,
  MetricBoard,
  OrgNode,
  OverviewResult,
  PermCatalog,
  ProjectItem,
  RoleItem,
  SummaryResult,
  TaskItem,
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
}

/* ---------------- 鉴权 ---------------- */
export const authApi = {
  login: (account: string, password: string) =>
    http.post<LoginResult>('/auth/login', { account, password }).then((r) => r.data),
  logout: () => http.post('/auth/logout').then((r) => r.data),
  me: () => http.get<MeResult>('/auth/me').then((r) => r.data),
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

/* ---------------- 任务 ---------------- */
export const taskApi = {
  list: (params: { keyword?: string; dept_id?: string; status?: string; page?: number; size?: number } = {}) =>
    http.get<{ items: TaskItem[]; total: number; page: number; size: number }>('/tasks', { params }).then((r) => r.data),
  detail: (id: string) => http.get<TaskItem>(`/tasks/${id}`).then((r) => r.data),
  create: (payload: Record<string, unknown>) => http.post<TaskItem>('/tasks', payload).then((r) => r.data),
  update: (id: string, payload: Record<string, unknown>) => http.patch<TaskItem>(`/tasks/${id}`, payload).then((r) => r.data),
  remove: (id: string) => http.delete(`/tasks/${id}`).then((r) => r.data),
  deptStats: () => http.get<DeptTaskStat[]>('/tasks/dept-stats').then((r) => r.data),
  importFile: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post<ImportResult>('/tasks/import', fd).then((r) => r.data)
  },
  templateUrl: () => '/api/v1/tasks/import/template',
  exportUrl: () => '/api/v1/tasks/export',
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
