import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi } from '@/api'
import { TOKEN_KEY } from '@/api/http'
import type { UserBrief } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserBrief | null>(null)
  const perms = ref<string[]>([])
  const visibleOrgs = ref<string[]>([])
  const ready = ref(false)

  const isLoggedIn = computed(() => !!token.value && !!user.value)

  function setToken(value: string | null) {
    token.value = value
    if (value) localStorage.setItem(TOKEN_KEY, value)
    else localStorage.removeItem(TOKEN_KEY)
  }

  async function login(account: string, password: string) {
    const data = await authApi.login(account, password)
    setToken(data.access_token)
    user.value = data.user
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
      user.value = data.user
      perms.value = data.perms
      visibleOrgs.value = data.visibleOrgs
    } catch {
      clear()
    } finally {
      ready.value = true
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

  return { token, user, perms, visibleOrgs, ready, isLoggedIn, scope, login, logout, fetchMe, clear, hasPerm, hasAnyPerm }
})
