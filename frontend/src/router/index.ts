import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
// 登录页是首屏必经路径（未登录必然停在这里），改为静态导入打进主包：
// 懒加载会让首屏多一轮「主包 → 登录页 chunk」的网络往返，线上约 300-400ms。
import LoginView from '@/views/LoginView.vue'

/** 页面 → 所需菜单权限（与后端 constants.PAGE_PERM 一致） */
export const PAGE_PERM: Record<string, string> = {
  dashboard: 'dashboard.view',
  tasks: 'task.view',
  metrics: 'metric.view',
  accounts: 'account.view',
  market: 'market.view',
  dict: 'sys.config.view',
  downloads: 'download.view',
  doc: 'sys.config.view',
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        { path: '', redirect: '/dashboard' },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '经营驾驶舱', perm: 'dashboard.view' },
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: () => import('@/views/TasksView.vue'),
          meta: { title: '任务管理', perm: 'task.view' },
        },
        {
          path: 'market',
          name: 'market',
          component: () => import('@/views/ProjectsView.vue'),
          meta: { title: '项目管理', perm: 'market.view' },
        },
        {
          path: 'metrics',
          name: 'metrics',
          component: () => import('@/views/MetricsView.vue'),
          meta: { title: '指标维护', perm: 'metric.view' },
        },
        {
          path: 'accounts',
          name: 'accounts',
          component: () => import('@/views/AccountsView.vue'),
          meta: { title: '账号管理', perm: 'account.view' },
        },
        {
          path: 'dict',
          name: 'dict',
          component: () => import('@/views/SysDictView.vue'),
          meta: { title: '数据字典', perm: 'sys.config.view' },
        },
        {
          path: 'downloads',
          name: 'downloads',
          component: () => import('@/views/DownloadsView.vue'),
          meta: { title: '下载中心', perm: 'download.view' },
        },
        {
          path: 'doc',
          name: 'doc',
          component: () => import('@/views/DocView.vue'),
          meta: { title: '使用说明', perm: 'sys.config.view' },
        },
        {
          path: 'forbidden',
          name: 'forbidden',
          component: () => import('@/views/ForbiddenView.vue'),
          meta: { title: '无访问权限' },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.fetchMe()

  if (to.meta.public) {
    if (auth.isLoggedIn && to.name === 'login') return { name: 'dashboard' }
    return true
  }

  if (!auth.isLoggedIn) {
    return { name: 'login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }

  const perm = to.meta.perm as string | undefined
  if (perm && !auth.hasPerm(perm)) return { name: 'forbidden' }
  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string) || ''
  document.title = title ? `${title} · 合一重卡生态经营看板` : '合一重卡生态经营看板'
})

export default router
