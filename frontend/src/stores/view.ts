import { defineStore } from 'pinia'
import { ref } from 'vue'

import { clampMonth } from '@/constants/period'

/** 跨页面共享的视图上下文：周期、取数组织、指标定位 */
export const useViewStore = defineStore('view', () => {
  const period = ref('')
  const currentPeriod = ref('')
  const dataAsOf = ref('')
  /**
   * 取数组织的 ID。驾驶舱与指标维护**固定用全公司（CO）口径**。
   *
   * 本系统里全公司与项目公司并非递归汇总关系——项目公司只承载运营收入，
   * 销售收入由系统中未体现的主体产生——因此不做「组织视角」切换，
   * 也不按登录人的数据可见范围裁剪：这两个模块只按角色权限判断能否查看。
   * 数据可见范围（scope）**仅作用于任务模块**。
   * 项目公司的明细仍在指标维护页按行并列展示，那是维护入口，不是视角切换。
   */
  const orgId = ref('CO')
  /** 从驾驶舱「去维护」跳转时的定位目标 */
  const focusMetric = ref<{ metricId: string; orgId: string } | null>(null)
  /** 视图上下文（周期）是否已就绪；未就绪前页面不发请求，避免首帧参数为空 */
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
