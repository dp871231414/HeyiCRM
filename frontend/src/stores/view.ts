import { defineStore } from 'pinia'
import { ref } from 'vue'

import { clampMonth } from '@/constants/period'

/** 跨页面共享的视图上下文：周期、当前数据范围、指标定位 */
export const useViewStore = defineStore('view', () => {
  const period = ref('')
  const currentPeriod = ref('')
  const dataAsOf = ref('')
  /**
   * 当前数据范围的组织 ID：由登录人的可见范围决定（全公司范围 → CO，部门范围 → 所属部门）。
   *
   * 这里**不提供「组织视角」切换**。本系统里全公司与项目公司并非递归汇总关系
   * ——项目公司只承载运营收入，销售收入由系统中未体现的主体产生——
   * 允许切到某个项目公司去看，容易让人误以为「全公司 = 各项目公司之和」。
   * 项目公司的明细仍在指标维护页按行并列展示，那是维护入口，不是视角切换。
   */
  const orgId = ref('CO')
  /** 从驾驶舱「去维护」跳转时的定位目标 */
  const focusMetric = ref<{ metricId: string; orgId: string } | null>(null)
  /** 数据范围是否已按当前登录人的可见范围解析完成（未完成前页面不发请求，避免首帧越权 403） */
  const contextReady = ref(false)

  /**
   * 记录服务端给出的当前周期与数据截至日。
   *
   * 周期本身由页面内的月份选择器维护（可选范围见 constants/period），
   * 这里只负责初始化与范围收敛，不再从「有数据的月份」推导可选项。
   */
  function setPeriods(current: string, asOf: string) {
    currentPeriod.value = current
    dataAsOf.value = asOf
    period.value = clampMonth(period.value || current)
  }

  function setPeriod(value: string) {
    period.value = clampMonth(value)
  }

  function gotoMetric(metricId: string, orgIdValue: string) {
    focusMetric.value = { metricId, orgId: orgIdValue }
  }

  function consumeFocus(): { metricId: string; orgId: string } | null {
    const f = focusMetric.value
    focusMetric.value = null
    return f
  }

  return {
    period,
    currentPeriod,
    dataAsOf,
    orgId,
    focusMetric,
    contextReady,
    setPeriods,
    setPeriod,
    gotoMetric,
    consumeFocus,
  }
})
