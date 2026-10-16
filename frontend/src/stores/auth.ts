import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi, prefsApi } from '@/api'
import { TOKEN_KEY } from '@/api/http'
import type { UserBrief } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserBrief | null>(null)
  const perms = ref<string[]>([])
  const visibleOrgs = ref<string[]>([])
  /** 用户级偏好（行高 rowHeight 等），按账号记忆，登录/me 时载入 */
  const preferences = ref<Record<string, unknown>>({})
  const ready = ref(false)

  const isLoggedIn = computed(() => !!token.value && !!user.value)

  /** 当前行高：default / high / ultra，缺省 default */
  const rowHeight = computed(() => (preferences.value.rowHeight as string) || 'default')

  function setToken(value: string | null) {
    token.value = value
    if (value) localStorage.setItem(TOKEN_KEY, value)
    else localStorage.removeItem(TOKEN_KEY)
  }

  function applyUser(u: UserBrief | null) {
    user.value = u
    if (u?.preferences) preferences.value = { ...u.preferences }
    else preferences.value = {}
  }

  async function login(account: string, password: string) {
    const data = await authApi.login(account, password)
    setToken(data.access_token)
    applyUser(data.user)
    perms.value = data.perms
    ready.value = true
  }

  async function fetchMe() {
    if (!token.value) {
      ready.value = true
      return
    }
    try {
      const data = await authApi.me()
      applyUser(data.user)
      perms.value = data.perms
      visibleOrgs.value = data.visibleOrgs
    } catch {
      clear()
    } finally {
      ready.value = true
    }
  }

  /** 更新偏好：浅合并后写入后端并同步本地状态（按账号记忆，下次登录仍生效） */
  async function updatePreferences(patch: Record<string, unknown>) {
    const next = { ...preferences.value, ...patch }
    preferences.value = next
    if (user.value) applyUser({ ...user.value, preferences: next })
    try {
      const res = await prefsApi.update(patch)
      preferences.value = res.preferences || next
      if (user.value) applyUser({ ...user.value, preferences: res.preferences || next })
    } catch (e) {
      // 网络失败不阻断界面；本地状态已乐观更新
      throw e
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      /* 忽略登出接口异常，前端照常清理 */
    }
    clear()
  }

  function clear() {
    setToken(null)
    user.value = null
    perms.value = []
    visibleOrgs.value = []
  }

  function hasPerm(perm: string) {
    return perms.value.includes(perm)
  }

  function hasAnyPerm(list: string[]) {
    return list.some((p) => perms.value.includes(p))
  }

  const scope = computed(() => user.value?.scope ?? 'self')

  return {
    token,
    user,
    perms,
    visibleOrgs,
    preferences,
    ready,
    isLoggedIn,
    scope,
    rowHeight,
    login,
    logout,
    fetchMe,
    clear,
    hasPerm,
    hasAnyPerm,
    updatePreferences,
  }
})
