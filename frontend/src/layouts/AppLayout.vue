<template>
  <div class="min-h-screen flex bg-slate-50">
    <!-- 侧边栏 -->
    <aside
      class="fixed inset-y-0 left-0 z-40 bg-white border-r border-slate-200 flex flex-col transition-all duration-200"
      :class="collapsed ? 'w-[64px]' : 'w-[232px]'"
    >
      <div class="h-16 flex items-center gap-2.5 px-4 border-b border-slate-200 shrink-0">
        <div
          class="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-600 to-brand-400 text-white grid place-items-center font-extrabold text-sm shrink-0 shadow-[0_4px_14px_rgba(0,82,255,0.35)]"
        >
          合
        </div>
        <div v-if="!collapsed" class="min-w-0">
          <div class="text-[13px] font-extrabold text-slate-900 leading-tight truncate tracking-display">
            合一重卡生态
          </div>
          <div class="text-[11px] text-slate-400 leading-tight">经营看板</div>
        </div>
      </div>

      <nav class="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
        <template v-for="item in menus" :key="item.name || item.label">
          <!-- 含子菜单的分组（如 系统配置 → 数据字典） -->
          <div v-if="item.children" class="space-y-1">
            <button
              type="button"
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ease-out text-slate-600 hover:bg-brand-50/70 hover:text-brand-700"
              :title="collapsed ? item.label : ''"
              @click="groupOpen[item.label] = !groupOpen[item.label]"
            >
              <span class="w-4 text-center shrink-0" v-html="item.icon" />
              <span v-if="!collapsed" class="flex-1 text-left">{{ item.label }}</span>
              <svg
                v-if="!collapsed"
                class="w-3.5 h-3.5 text-slate-400 transition-transform duration-200"
                :class="groupOpen[item.label] ? 'rotate-90' : ''"
                viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              >
                <path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
            <div v-show="!collapsed && groupOpen[item.label]" class="pl-4 space-y-1">
              <router-link
                v-for="c in item.children"
                :key="c.name"
                :to="{ name: c.name }"
                class="flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-200 ease-out"
                :class="
                  route.name === c.name
                    ? 'bg-gradient-to-r from-brand-600 to-brand-400 text-white shadow-btn'
                    : 'text-slate-600 hover:bg-brand-50/70 hover:text-brand-700'
                "
              >
                <span class="w-4 text-center shrink-0" v-html="c.icon" />
                <span>{{ c.label }}</span>
              </router-link>
            </div>
          </div>
          <!-- 普通菜单 -->
          <router-link
            v-else
            :to="{ name: item.name }"
            class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ease-out"
            :class="
              route.name === item.name
                ? 'bg-gradient-to-r from-brand-600 to-brand-400 text-white shadow-btn'
                : 'text-slate-600 hover:bg-brand-50/70 hover:text-brand-700'
            "
            :title="collapsed ? item.label : ''"
          >
            <span class="w-4 text-center shrink-0" v-html="item.icon" />
            <span v-if="!collapsed">{{ item.label }}</span>
          </router-link>
        </template>
      </nav>

      <div v-if="!collapsed" class="px-4 py-3 border-t border-slate-200 text-[11px] text-slate-400">
        数据截至 <span class="tabular-nums">{{ view.dataAsOf || '—' }}</span>
      </div>
    </aside>

    <!-- 主区 -->
    <div class="flex-1 flex flex-col min-w-0 transition-all duration-200" :class="collapsed ? 'ml-[64px]' : 'ml-[232px]'">
      <header
        class="h-16 sticky top-0 z-30 bg-white/85 backdrop-blur border-b border-slate-200 flex items-center gap-3 px-5"
      >
        <button class="btn-ghost btn-sm" @click="app.toggleSidebar()" title="收起/展开菜单">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18M3 12h18M3 18h18" stroke-linecap="round" />
          </svg>
        </button>
        <h1 class="text-[15px] font-extrabold tracking-display text-slate-900">{{ title }}</h1>

        <div class="ml-auto flex items-center gap-2">
          <div class="relative">
            <button
              class="flex items-center gap-2 px-2.5 py-1.5 rounded-xl transition hover:bg-brand-50/70"
              @click="menuOpen = !menuOpen"
            >
              <span
                class="w-7 h-7 rounded-full bg-gradient-to-br from-brand-500 to-brand-400 text-white grid place-items-center text-xs font-bold"
              >
                {{ (auth.user?.name || '?').slice(0, 1) }}
              </span>
              <span class="hidden sm:block text-left leading-tight">
                <span class="block text-xs font-bold text-slate-800">{{ auth.user?.name }}</span>
                <span class="block text-[10px] text-slate-400">{{ auth.user?.roleName }}</span>
              </span>
            </button>
            <div
              v-if="menuOpen"
              class="absolute right-0 mt-1 w-52 bg-white rounded-xl border border-slate-200 shadow-pop py-1.5 z-50"
            >
              <div class="px-3.5 py-2 border-b border-slate-100">
                <div class="text-xs font-bold text-slate-800">{{ auth.user?.name }} · {{ auth.user?.account }}</div>
                <div class="text-[11px] text-slate-400">
                  {{ auth.user?.deptName }} / {{ auth.user?.roleName }}
                </div>
                <div class="text-[11px] text-slate-400">可见范围：{{ scopeLabel }}</div>
              </div>
              <button
                class="w-full text-left px-3.5 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-bad-600"
                @click="doLogout"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>
      </header>

      <main class="flex-1 p-5 max-w-content w-full mx-auto min-w-0">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { metricApi } from '@/api'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useViewStore } from '@/stores/view'

const app = useAppStore()
const auth = useAuthStore()
const view = useViewStore()
const route = useRoute()
const router = useRouter()

const collapsed = computed(() => app.sidebarCollapsed)
const title = computed(() => (route.meta.title as string) || '')
const menuOpen = ref(false)
/** 含子菜单的分组展开状态（默认展开） */
const groupOpen = reactive<Record<string, boolean>>({
  系统配置: true,
})
const SCOPE_TEXT: Record<string, string> = {
  self: '本人',
  dept: '本部门',
  dept_sub: '本部门及下属部门',
  all: '全公司',
}
const scopeLabel = computed(() => SCOPE_TEXT[auth.scope] ?? auth.scope)

const ICONS: Record<string, string> = {
  dashboard:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>',
  tasks:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6h11M9 12h11M9 18h11" stroke-linecap="round"/><circle cx="4.5" cy="6" r="1.5"/><circle cx="4.5" cy="12" r="1.5"/><circle cx="4.5" cy="18" r="1.5"/></svg>',
  market:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7l9-4 9 4-9 4-9-4z" stroke-linejoin="round"/><path d="M3 7v10l9 4 9-4V7" stroke-linejoin="round"/><path d="M12 11v10"/></svg>',
  metrics:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 20h18" stroke-linecap="round"/><path d="M6 16l4-6 3 4 5-8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  accounts:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="3.4"/><path d="M4.5 20c1.2-3.6 4-5.4 7.5-5.4S18.3 16.4 19.5 20" stroke-linecap="round"/></svg>',
  system:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" stroke-linejoin="round"/></svg>',
  dict:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round"/></svg>',
  download:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12" stroke-linecap="round"/><path d="M7 11l5 5 5-5" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 20h16" stroke-linecap="round"/></svg>',
  doc:
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2h9l5 5v15a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z" stroke-linejoin="round"/><path d="M14 2v6h6" stroke-linejoin="round"/><path d="M9 13h6M9 17h6" stroke-linecap="round"/></svg>',
}

type MenuItem = {
  name?: string
  label: string
  perm: string
  icon: string
  children?: { name: string; label: string; perm: string; icon: string }[]
}

const ALL_MENUS: MenuItem[] = [
  { name: 'dashboard', label: '经营驾驶舱', perm: 'dashboard.view', icon: ICONS.dashboard },
  { name: 'tasks', label: '任务管理', perm: 'task.view', icon: ICONS.tasks },
  { name: 'market', label: '项目管理', perm: 'market.view', icon: ICONS.market },
  { name: 'metrics', label: '指标维护', perm: 'metric.view', icon: ICONS.metrics },
  {
    label: '系统配置',
    perm: 'sys.config.view',
    icon: ICONS.system,
    children: [
      { name: 'dict', label: '数据字典', perm: 'sys.config.view', icon: ICONS.dict },
      { name: 'accounts', label: '账号管理', perm: 'account.view', icon: ICONS.accounts },
      { name: 'downloads', label: '下载中心', perm: 'download.view', icon: ICONS.download },
      { name: 'doc', label: '文档中心', perm: 'doc.view', icon: ICONS.doc },
    ],
  },
]
const menus = computed<MenuItem[]>(() => {
  const mapped = ALL_MENUS.map((m): MenuItem | null => {
    if (m.children) {
      const kids = m.children.filter((c) => auth.hasPerm(c.perm))
      if (!kids.length || !auth.hasPerm(m.perm)) return null
      return { ...m, children: kids }
    }
    return auth.hasPerm(m.perm) ? m : null
  })
  return mapped.filter((m): m is MenuItem => m !== null)
})

async function loadContext() {
  if (!auth.token) return
  view.contextReady = false

  const periodRes = await metricApi.periods().catch(() => null)
  if (periodRes) view.setPeriods(periodRes.current, periodRes.dataAsOf)

  // 数据口径：驾驶舱与指标维护**只按角色权限**判断能否查看，一律按全公司口径取数。
  //   · 全公司与项目公司不是递归汇总关系（项目公司只承载运营收入），
  //     按部门可见范围裁剪经营数据反而会让人误读口径；
  //   · 数据可见范围（scope）**只作用于任务模块**，不参与此处的取数。
  view.orgId = 'CO'
  view.contextReady = true
}

function onDocClick(e: MouseEvent) {
  const el = e.target as HTMLElement
  if (!el.closest('.relative')) menuOpen.value = false
}

async function doLogout() {
  menuOpen.value = false
  await auth.logout()
  router.push({ name: 'login' })
}

// 仅在已登录时重载上下文；登出后不再发请求（避免 401 噪声）
watch(
  () => auth.user?.id,
  (id) => {
    if (id) loadContext()
  },
)
onMounted(() => {
  document.addEventListener('click', onDocClick)
  loadContext()
})
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>
