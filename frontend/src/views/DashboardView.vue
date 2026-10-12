<template>
  <div class="space-y-5">
    <!-- 统计周期（页面内选择；顶栏不再展示，任务管理页亦不展示） -->
    <div class="flex flex-wrap items-center gap-3">
      <MonthPicker v-model="view.period" />
      <span class="text-xs text-slate-400">数据截至 {{ view.dataAsOf || '—' }}</span>
    </div>

    <!-- 错误态 -->
    <div v-if="error" class="card p-4 border-bad-100 bg-bad-50 flex items-center gap-3">
      <span class="text-bad-600">加载失败：{{ error }}</span>
      <button class="btn-ghost btn-sm" @click="load">重试</button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="card p-10 text-center text-slate-400 text-sm">数据加载中…</div>

    <!-- 本人范围：无组织维度数据 -->
    <div v-else-if="noOrgDimension" class="card p-8 text-center space-y-2">
      <div class="text-sm font-bold text-slate-700">当前账号的数据可见范围为「本人」</div>
      <p class="text-xs text-slate-500 leading-relaxed">
        按权限设计，「本人」范围不含组织维度的经营指标数据，驾驶舱无内容可展示。<br />
        你仍可在「任务管理」中查看与维护本人负责的任务；如需查看经营指标，
        请联系管理员将数据可见范围调整为「本部门」或更高。
      </p>
    </div>

    <template v-else-if="summary && overview">
      <!-- 分析总结 -->
      <section class="card p-5" :class="toneBorder">
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <div class="flex items-center gap-2 mb-2">
              <span class="chip border" :class="toneChip">{{ toneText }}</span>
              <span class="text-xs text-slate-400">{{ overview.period }} · {{ overview.orgName }}</span>
            </div>
            <p class="text-[15px] leading-relaxed text-slate-800 font-medium">{{ summary.headline }}</p>
          </div>
          <div class="hidden lg:flex gap-2 shrink-0">
            <div v-for="c in countCards" :key="c.label" class="text-center px-3.5 py-2 rounded-lg bg-white border border-slate-200">
              <div class="text-lg font-extrabold" :class="c.cls">{{ c.value }}</div>
              <div class="text-[11px] text-slate-400">{{ c.label }}</div>
            </div>
          </div>
        </div>

        <div v-if="summary.wins.length" class="mt-4 grid md:grid-cols-2 gap-x-6 gap-y-1.5">
          <div v-for="(w, i) in summary.wins" :key="i" class="flex gap-2 text-sm text-slate-600">
            <span class="text-good-600 font-bold shrink-0">亮点</span><span>{{ w }}</span>
          </div>
        </div>

        <div v-if="summary.points.length" class="mt-4 pt-4 border-t border-slate-200 space-y-1.5">
          <div v-for="(p, i) in summary.points" :key="i" class="flex gap-2 text-sm text-slate-600">
            <span class="text-brand-600 font-bold shrink-0">建议 {{ i + 1 }}</span><span>{{ p }}</span>
          </div>
        </div>
      </section>

      <!-- 核心指标 -->
      <section>
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-bold text-slate-900">核心指标 · 年度目标</h2>
          <span class="text-xs text-slate-400">
            累计完成值为「截止当月」的累计值{{ snapshotHint }}
          </span>
        </div>

        <div v-if="deptView" class="card p-8 text-center text-xs text-slate-500 leading-relaxed">
          指标目标只下达在<b class="text-slate-700">公司与项目公司</b>层级，{{ overview.orgName }} 暂无独立指标数据。<br />
          本页可查看本部门的任务完成度与风险提示；公司整体经营指标需要相应的数据权限。
        </div>

        <div v-else class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <button
            v-for="row in revenueRows"
            :key="row.metricId"
            class="card p-4 text-left transition hover:shadow-cardHover"
            @click="openDrilldown(row)"
          >
            <div class="flex items-center justify-between">
              <span class="text-[13px] font-bold text-slate-700">{{ row.name }}</span>
              <StatusBadge :light="row.light" />
            </div>
            <div class="mt-3 flex items-baseline gap-1.5">
              <span class="text-2xl font-extrabold text-slate-900">{{ fmt(row.actual) }}</span>
              <span class="text-xs text-slate-400">/ {{ fmt(row.target) }} {{ row.unit }}</span>
            </div>
            <div class="mt-2.5 h-2 rounded-full bg-slate-100 overflow-hidden">
              <div class="h-full rounded-full transition-all" :class="barClass(row.light)" :style="{ width: barWidth(row) }" />
            </div>
            <div class="mt-2 flex items-center justify-between text-xs">
              <span class="font-bold" :class="rateClass(row.light)">{{ row.rateText }}</span>
              <span :class="vsClass(row.vsTime)">vs 时间进度 {{ fmtDelta(row.vsTime) }}</span>
            </div>
            <div v-if="row.hasCollection" class="mt-2.5 pt-2.5 border-t border-slate-100 flex items-center justify-between text-xs">
              <span class="text-slate-500">回款率（{{ fmt(row.collActual) }} / {{ fmt(row.actual) }}）</span>
              <StatusBadge :light="row.collLight" :text="fmtPct(row.collRate)" />
            </div>
          </button>
        </div>

        <div v-if="!deptView" class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
          <div v-for="row in simpleRows" :key="row.metricId" class="card p-4">
            <div class="flex items-center justify-between">
              <span class="text-[13px] font-bold text-slate-700">{{ row.name }}</span>
              <StatusBadge :light="row.light" />
            </div>
            <div class="mt-3 flex items-baseline gap-1.5">
              <span class="text-2xl font-extrabold text-slate-900">{{ fmt(row.actual) }}</span>
              <span class="text-xs text-slate-400">/ {{ fmt(row.target) }} {{ row.unit }}</span>
            </div>
            <div class="mt-2 flex items-center justify-between text-xs">
              <span class="font-bold" :class="rateClass(row.light)">{{ row.rateText }}</span>
              <span :class="vsClass(row.vsTime)">vs 时间进度 {{ fmtDelta(row.vsTime) }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 项目公司对比 -->
      <section v-if="overview.projectCompare.length">
        <h2 class="text-sm font-bold text-slate-900 mb-3">项目公司经营对比</h2>
        <div class="card overflow-x-auto">
          <table class="w-full min-w-[760px]">
            <thead>
              <tr class="border-b border-slate-200">
                <th class="th">项目公司</th>
                <th v-for="m in overview.projectMetrics" :key="m.id" class="th text-right">
                  {{ m.name }}{{ m.snapshot ? '（期末）' : '' }}
                </th>
                <th class="th text-right">完成率</th>
                <th class="th text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in overview.projectCompare" :key="c.orgId" class="border-b border-slate-100 last:border-0">
                <td class="td">
                  <div class="font-semibold text-slate-800">{{ c.name }}</div>
                  <div class="text-[11px] text-slate-400">负责人 {{ c.head }} · 已录 {{ c.filled }}/{{ c.total }}</div>
                </td>
                <td v-for="m in overview.projectMetrics" :key="m.id" class="td text-right">
                  <div class="font-mono text-slate-800">{{ fmt(cellOf(c, m.id)?.actual) }}</div>
                  <div class="text-[11px] text-slate-400">目标 {{ fmt(cellOf(c, m.id)?.target) }}</div>
                </td>
                <td class="td text-right">
                  <span class="font-bold" :class="c.completion === null ? 'text-slate-400' : c.completion >= 0.98 ? 'text-good-600' : c.completion >= 0.9 ? 'text-warn-600' : 'text-bad-600'">
                    {{ fmtPct(c.completion) }}
                  </span>
                </td>
                <td class="td text-right">
                  <button class="btn-ghost btn-sm" @click="gotonMetric('OP_REV', c.orgId)">去维护</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 监控指标 -->
      <section v-if="overview.monitor.length">
        <h2 class="text-sm font-bold text-slate-900 mb-3">指标监控 · {{ overview.period }}</h2>
        <div class="card p-4 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
          <div v-for="row in overview.monitor" :key="row.metricId" class="rounded-lg border border-slate-200 px-3.5 py-3">
            <div class="text-xs text-slate-500">{{ row.name }}</div>
            <div class="mt-1.5 text-xl font-extrabold text-slate-900">
              {{ fmt(row.actual) }}<span class="text-xs font-medium text-slate-400 ml-1">{{ row.unit }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 部门任务完成度 -->
      <section v-if="overview.deptTaskStats.length">
        <h2 class="text-sm font-bold text-slate-900 mb-3">部门任务完成度</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <div
            v-for="d in overview.deptTaskStats"
            :key="d.deptId"
            class="card p-4"
            :class="d.overdue + d.risk > 0 ? 'border-bad-100' : ''"
          >
            <div class="flex items-center justify-between">
              <span class="text-[13px] font-bold text-slate-800">{{ d.deptName }}</span>
              <span class="text-[11px] text-slate-400">{{ d.total }} 项任务</span>
            </div>
            <div class="mt-3 flex items-baseline gap-1">
              <span class="text-2xl font-extrabold text-slate-900">{{ d.completion }}%</span>
              <span class="text-[11px] text-slate-400">平均完成度</span>
            </div>
            <div class="mt-3 flex flex-wrap gap-1.5 text-[11px]">
              <span class="chip bg-good-50 text-good-700 border border-good-100">已完成 {{ d.done }}</span>
              <span v-if="d.overdue" class="chip bg-bad-50 text-bad-700 border border-bad-100">逾期 {{ d.overdue }}</span>
              <span v-if="d.risk" class="chip bg-bad-50 text-bad-700 border border-bad-100">异常 {{ d.risk }}</span>
              <span v-if="d.dueSoon" class="chip bg-warn-50 text-warn-700 border border-warn-100">临期 {{ d.dueSoon }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 风险与异常（文末） -->
      <section>
        <h2 class="text-sm font-bold text-slate-900 mb-3">风险与异常</h2>
        <div class="card divide-y divide-slate-100">
          <div v-if="!summary.risks.length" class="px-4 py-6 text-sm text-slate-400 text-center">
            本周期未发现风险项
          </div>
          <div
            v-for="(r, i) in summary.risks"
            :key="i"
            class="px-4 py-3 flex items-start gap-3 hover:bg-slate-50 cursor-pointer"
            @click="onRiskClick(r)"
          >
            <span class="chip border shrink-0 mt-0.5" :class="riskChip(r.type)">
              {{ riskLabel(r.type) }}
            </span>
            <span class="text-sm text-slate-700">{{ r.text }}</span>
          </div>
        </div>
      </section>
    </template>

    <!-- 指标下钻 -->
    <ModalDialog :open="!!drill" :title="drill ? `${drill.name} · 趋势` : ''" @close="drill = null">
      <div v-if="drill">
        <div class="flex items-center gap-3 mb-4">
          <StatusBadge :light="drill.light" />
          <span class="text-sm text-slate-500">
            目标 {{ fmt(drill.target) }} / 完成 {{ fmt(drill.actual) }} {{ drill.unit }} · 达成率 {{ drill.rateText }}
          </span>
        </div>
        <div v-if="trendLoading" class="py-10 text-center text-sm text-slate-400">加载趋势中…</div>
        <template v-else-if="trend && trend.points.length">
          <Sparkline :values="trend.points.map((p) => p.value)" :height="140" />
          <div class="flex justify-between text-[11px] text-slate-400 mt-2">
            <span>{{ trend.points[0].period }}</span>
            <span>{{ trend.points[trend.points.length - 1].period }}</span>
          </div>
          <table class="w-full mt-4">
            <thead>
              <tr class="border-b border-slate-200">
                <th class="th">周期</th>
                <th class="th text-right">数值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in trend.points" :key="p.period" class="border-b border-slate-50 last:border-0">
                <td class="td">{{ p.period }}</td>
                <td class="td text-right font-mono">{{ fmt(p.value) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <div v-else class="py-10 text-center text-sm text-slate-400">暂无历史数据</div>
      </div>
    </ModalDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { dashboardApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import MonthPicker from '@/components/MonthPicker.vue'
import Sparkline from '@/components/Sparkline.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { useViewStore } from '@/stores/view'
import type { MetricRow, OverviewResult, ProjectCompanyBlock, SummaryResult, TrendResult } from '@/types'
import { fmt, fmtDelta, fmtPct } from '@/utils/format'

const view = useViewStore()
const auth = useAuthStore()
const router = useRouter()

const loading = ref(false)
const error = ref('')
const summary = ref<SummaryResult | null>(null)
const overview = ref<OverviewResult | null>(null)

const drill = ref<MetricRow | null>(null)
const trend = ref<TrendResult | null>(null)
const trendLoading = ref(false)

const revenueRows = computed(() => (overview.value?.annual ?? []).filter((r) => r.family === 'revenue'))
const simpleRows = computed(() => (overview.value?.annual ?? []).filter((r) => r.family !== 'revenue'))
const snapshotHint = computed(() =>
  (overview.value?.annual ?? []).some((r) => r.snapshot) ? '；运营车辆为期末快照' : '',
)

const toneText = computed(
  () => ({ good: '整体良好', warn: '需要关注', bad: '存在风险', none: '暂无数据' })[summary.value?.tone ?? 'none'],
)
const toneChip = computed(
  () =>
    ({
      good: 'bg-good-50 text-good-700 border-good-100',
      warn: 'bg-warn-50 text-warn-700 border-warn-100',
      bad: 'bg-bad-50 text-bad-700 border-bad-100',
      none: 'bg-slate-100 text-slate-600 border-slate-200',
    })[summary.value?.tone ?? 'none'],
)
const toneBorder = computed(() =>
  summary.value?.tone === 'bad' ? 'border-bad-100' : summary.value?.tone === 'warn' ? 'border-warn-100' : 'border-slate-200',
)

const countCards = computed(() => {
  const c = summary.value?.counts
  if (!c) return []
  return [
    { label: '达标', value: c.green, cls: 'text-good-600' },
    { label: '接近', value: c.amber, cls: 'text-warn-600' },
    { label: '未达标', value: c.red, cls: 'text-bad-600' },
    { label: '未录入', value: c.none, cls: 'text-slate-400' },
  ]
})

function barWidth(row: MetricRow) {
  const rate = row.rate ?? 0
  return `${Math.min(100, Math.max(2, (rate === Infinity ? 1 : rate) * 100))}%`
}
function barClass(light: string) {
  return { green: 'bg-good-500', amber: 'bg-warn-500', red: 'bg-bad-500', none: 'bg-slate-300' }[light] ?? 'bg-slate-300'
}
function rateClass(light: string) {
  return { green: 'text-good-600', amber: 'text-warn-600', red: 'text-bad-600', none: 'text-slate-400' }[light] ?? 'text-slate-400'
}
function vsClass(v: number | null) {
  if (v === null) return 'text-slate-400'
  return v >= 0 ? 'text-good-600' : 'text-bad-600'
}
function cellOf(c: ProjectCompanyBlock, metricId: string) {
  return c.cells.find((x) => x.metricId === metricId)
}
const RISK_LABEL: Record<string, string> = { indicator: '指标', monitor: '监控', task: '任务' }
const RISK_CHIP: Record<string, string> = {
  indicator: 'bg-bad-50 text-bad-700 border-bad-100',
  monitor: 'bg-warn-50 text-warn-700 border-warn-100',
  task: 'bg-brand-50 text-brand-700 border-brand-100',
}
const riskLabel = (t: string) => RISK_LABEL[t] ?? '风险'
const riskChip = (t: string) => RISK_CHIP[t] ?? 'bg-slate-100 text-slate-600 border-slate-200'

function onRiskClick(r: { type: string; org: string }) {
  if (r.type === 'task') router.push({ name: 'tasks' })
  else gotonMetric('REV_SALE', r.org || view.orgId)
}

function gotonMetric(metricId: string, orgId: string) {
  view.gotoMetric(metricId, orgId)
  router.push({ name: 'metrics' })
}

async function openDrilldown(row: MetricRow) {
  drill.value = row
  trend.value = null
  trendLoading.value = true
  try {
    trend.value = await dashboardApi.trend(row.metricId, view.orgId)
  } catch {
    trend.value = null
  } finally {
    trendLoading.value = false
  }
}

/** 本人范围：无组织维度数据（与后端 visibleOrgs 口径一致） */
const noOrgDimension = computed(() => auth.scope === 'self')
/** 部门/班组视角：指标目标只下达在公司与项目公司层级，故无核心指标卡 */
const deptView = computed(() => ['dept', 'team'].includes(overview.value?.orgType ?? ''))

let loadSeq = 0
async function load() {
  if (!view.period || !view.contextReady) return
  const seq = ++loadSeq
  if (noOrgDimension.value) {
    loading.value = false
    error.value = ''
    summary.value = null
    overview.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    const [s, o] = await Promise.all([
      dashboardApi.summary(view.period, view.orgId),
      dashboardApi.overview(view.period, view.orgId),
    ])
    // 并发加载时丢弃过期响应，避免先到的 403 覆盖后到的成功结果
    if (seq !== loadSeq) return
    summary.value = s
    overview.value = o
  } catch (e) {
    if (seq !== loadSeq) return
    error.value = (e as Error).message
    summary.value = null
    overview.value = null
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

watch([() => view.period, () => view.orgId, () => view.contextReady], load, { immediate: true })
</script>
