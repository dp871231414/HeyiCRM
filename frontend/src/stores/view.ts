import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 跨页面共享的视图上下文：周期、组织视角、指标定位 */
export const useViewStore = defineStore('view', () => {
  const period = ref('')
  const currentPeriod = ref('')
  const dataAsOf = ref('')
  const orgId = ref('CO')
  const orgOptions = ref<{ id: string; name: string }[]>([{ id: 'CO', name: '全公司' }])
  /** 从驾驶舱「去维护」跳转时的定位目标 */
  const focusMetric = ref<{ metricId: string; orgId: string } | null>(null)
  /** 组织视角是否已按当前登录人的可见范围解析完成（未完成前页面不发请求，避免首帧越权 403） */
  const contextReady = ref(false)

  function setPeriods(list: string[], current: string, asOf: string) {
    currentPeriod.value = current
    dataAsOf.value = asOf
    if (!period.value) period.value = current
    if (list.length) {
      const available = list.includes(period.value) ? list : [period.value, ...list].filter(Boolean)
      period.value = available.includes(period.value) ? period.value : current
    }
  }

  function gotoMetric(metricId: string, orgIdValue: string) {
    focusMetric.value = { metricId, orgId: orgIdValue }
  }

  function consumeFocus(): { metricId: string; orgId: string } | null {
    const f = focusMetric.value
    focusMetric.value = null
    return f
  }

  return { period, currentPeriod, dataAsOf, orgId, orgOptions, focusMetric, contextReady, setPeriods, gotoMetric, consumeFocus }
})
