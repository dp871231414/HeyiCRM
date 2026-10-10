import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ToastItem {
  id: number
  type: 'success' | 'error' | 'info'
  text: string
}

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(localStorage.getItem('fleet_sidebar') === '1')
  const toasts = ref<ToastItem[]>([])
  let seq = 0

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem('fleet_sidebar', sidebarCollapsed.value ? '1' : '0')
  }

  function toast(text: string, type: ToastItem['type'] = 'success') {
    const id = ++seq
    toasts.value.push({ id, type, text })
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, 3200)
  }

  return { sidebarCollapsed, toasts, toggleSidebar, toast }
})
