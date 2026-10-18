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

    <template v-else-if="summary && overview">
      <!-- 分析总结 · 本期经营结论。
           用普通浅色卡 + 左侧语义色条承载状态，与页面其余卡片保持同一套观感
           （此前是深色反转卡，在数据型页面里与周围卡片割裂、观感偏重）。 -->
      <section class="card relative overflow-hidden p-5 pl-6">
        <div class="absolute inset-y-0 left-0 w-1" :class="toneAccent" />

        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <div class="flex items-center gap-2 mb-2">
              <span class="chip border" :class="toneChip">{{ toneText }}</span>
              <span class="text-xs text-slate-400">{{ overview.period }} · {{ overview.orgName }}</span>
            </div>
            <p class="text-[15px] leading-relaxed font-medium text-slate-800">{{ summary.headline }}</p>
          </div>
          <div class="hidden lg:flex gap-2 shrink-0">
            <div
              v-for="c in countCards"
              :key="c.label"
              class="text-center px-3.5 py-2 rounded-xl bg-slate-50 border border-slate-200"
            >
              <div class="text-lg stat-value" :class="c.cls">{{ c.value }}</div>
              <div class="text-[11px] text-slate-400">{{ c.label }}</div>
            </div>
          </div>
        </div>

        <div v-if="summary.wins.length" class="mt-4 grid md:grid-cols-2 gap-x-6 gap-y-1.5">
          <div v-for="(w, i) in summary.wins" :key="i" class="flex gap-2 text-sm text-slate-600">
            <span class="text-good-600 font-bold shrink-0">亮点</span><span>{{ w }}</span>
          </div>
        </div>

        <div
          v-if="summary.points.length"
          class="mt-4 pt-4 border-t border-slate-100 space-y-1.5"
        >
          <div v-for="(p, i) in summary.points" :key="i" class="flex gap-2 text-sm text-slate-600">
            <span class="text-brand-600 font-bold shrink-0">建议 {{ i + 1 }}</span><span>{{ p }}</span>
          </div>
        </div>
      </section>

      <!-- 核心指标 -->
      <section>
        <div class="flex items-center justify-between mb-3">
          <h2 class="section-title">核心指标 · 年度目标</h2>
          <span class="text-xs text-slate-400">
            累计完成值为「截止当月」的累计值{{ snapshotHint }}
          </span>
        </div>

        <div v-if="deptView" class="card p-8 text-center text-xs text-slate-500 leading-relaxed">
          指标目标只下达在<b class="text-slate-700">公司与项目公司</b>层级，{{ overview.orgName }} 暂无独立指标数据。<br />
          本页可查看该部门的任务完成度与风险提示。
        </div>

        <div v-else class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <button
            v-for="row in revenueRows"
            :key="row.metricId"
            class="card card-lift p-4 text-left"
            @click="openDrilldown(row)"
          >
            <div class="flex items-center justify-between">
              <span class="text-[13px] font-bold text-slate-700">{{ row.name }}</span>
              <span class="chip border" :class="TONE_CHIP[toneOf(row.tone)]">{{ TONE_LABEL[toneOf(row.tone)] }}</span>
            </div>
            <div class="mt-3 flex items-baseline gap-1.5">
              <span class="text-2xl stat-value text-slate-900">{{ fmt(row.actual) }}</span>
              <span class="text-xs text-slate-400">/ {{ fmt(row.target) }} {{ row.unit }}</span>
            </div>
            <div class="mt-2.5 h-2 rounded-full bg-slate-100 overflow-hidden">
              <div class="h-full rounded-full transition-all" :class="TONE_BAR[toneOf(row.tone)]" :style="{ width: barWidth(row) }" />
            </div>
            <div class="mt-2 flex items-center justify-between text-xs">
              <span class="font-bold" :class="TONE_TEXT[toneOf(row.tone)]">{{ row.rateText }}</span>
              <span class="text-slate-400">vs 时间进度 {{ fmtDelta(row.vsTime) }}</span>
            </div>
            <div v-if="row.hasCollection" class="mt-2.5 pt-2.5 border-t border-slate-100 flex items-center justify-between text-xs">
              <span class="text-slate-500">回款率（{{ fmt(row.collActual) }} / {{ fmt(row.actual) }}）</span>
              <span class="font-bold" :class="COLL_TEXT[lightTone(row.collLight)]">{{ fmtPct(row.collRate) }}</span>
            </div>
          </button>
        </div>

        <div v-if="!deptView" class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
          <div v-for="row in simpleRows" :key="row.metricId" class="card p-4">
            <div class="flex items-center justify-between">
              <span class="text-[13px] font-bold text-slate-700">{{ row.name }}</span>
              <span class="chip border" :class="TONE_CHIP[toneOf(row.tone)]">{{ TONE_LABEL[toneOf(row.tone)] }}</span>
            </div>
            <div class="mt-3 flex items-baseline gap-1.5">
              <span class="text-2xl stat-value text-slate-900">{{ fmt(row.actual) }}</span>
              <span class="text-xs text-slate-400">/ {{ fmt(row.target) }} {{ row.unit }}</span>
            </div>
            <div class="mt-2 flex items-center justify-between text-xs">
              <span class="font-bold" :class="TONE_TEXT[toneOf(row.tone)]">{{ row.rateText }}</span>
              <span class="text-slate-400">vs 时间进度 {{ fmtDelta(row.vsTime) }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 市场项目概览：项目/车辆/挂车三漏斗（各阶段当前数量）+ 按阶段转化概率加权的销量预测 -->
      <section v-if="funnel">
        <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 mb-3">
          <div class="flex items-baseline gap-2">
            <h2 class="section-title">市场项目概览</h2>
            <span class="text-xs text-slate-400">每层为对应阶段当前实有的数量（非累计）</span>
          </div>
          <button v-if="auth.hasPerm('dashboard.config')" class="btn-ghost btn-sm" @click="openFunnelConfig">
            配置转化概率
          </button>
        </div>

        <!-- 筛选标签：全部 + 市场部各二级部门（动态读取，随组织变化同步更新） -->
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2 mb-3">
          <span class="text-xs text-slate-400">按部门筛选</span>
          <div class="inline-flex gap-0.5 p-0.5 rounded-lg bg-slate-100">
            <button
              class="px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-200 ease-out"
              :class="funnelDept === '' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              @click="setFunnelDept('')"
            >
              全部
            </button>
            <button
              v-for="d in funnelDeptOptions"
              :key="d.id"
              class="px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-200 ease-out"
              :class="funnelDept === d.id ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              @click="setFunnelDept(d.id)"
            >
              {{ d.name }}
            </button>
          </div>
          <span v-if="funnelDept" class="text-xs text-slate-400">当前：{{ funnelDeptName }}</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <FunnelChart title="市场项目转化漏斗" :stages="funnel.stages" field="count" unit="个" />
          <FunnelChart title="车头需求漏斗（牵引车）" :stages="funnel.stages" field="tractor" unit="辆" />
          <FunnelChart title="挂车需求漏斗" :stages="funnel.stages" field="trailer" unit="辆" />
          <div class="card p-4 flex flex-col">
            <div class="flex items-center justify-between">
              <h3 class="text-[13px] font-bold text-slate-700">销量预测</h3>
              <span class="text-[11px] text-slate-400">按阶段转化概率加权</span>
            </div>
            <div class="mt-4 flex-1 flex flex-col justify-center gap-4">
              <div>
                <div class="text-xs text-slate-500">预测牵引车销量</div>
                <div class="mt-1 text-3xl stat-value text-brand-700">
                  {{ fmt(funnel.forecast.tractor) }}<span class="text-sm font-medium text-slate-400 ml-1">辆</span>
                </div>
              </div>
              <div class="border-t border-slate-100 pt-4">
                <div class="text-xs text-slate-500">预测挂车销量</div>
                <div class="mt-1 text-3xl stat-value text-brand-700">
                  {{ fmt(funnel.forecast.trailer) }}<span class="text-sm font-medium text-slate-400 ml-1">辆</span>
                </div>
              </div>
            </div>
            <div class="mt-3 text-[11px] text-slate-400 leading-relaxed">
              Σ（各项目需求 × 所在阶段转化概率）<br />
              当前概率 {{ probSummary }}
            </div>
          </div>
        </div>
      </section>

      <!-- 项目公司对比 -->
      <section v-if="overview.projectCompare.length">
        <h2 class="section-title mb-3">项目公司经营对比</h2>
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
                  <span class="font-bold" :class="TONE_TEXT[toneOf(c.completionTone)]">
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
        <h2 class="section-title mb-3">指标监控 · {{ overview.period }}</h2>
        <div class="card p-4 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
          <div v-for="row in overview.monitor" :key="row.metricId" class="rounded-lg border border-slate-200 px-3.5 py-3">
            <div class="text-xs text-slate-500">{{ row.name }}</div>
            <div class="mt-1.5 text-xl font-extrabold text-slate-900">
              {{ fmt(row.actual) }}<span class="text-xs font-medium text-slate-400 ml-1">{{ row.unit }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 部门任务完成度 · 展示口径可切换（默认全部），任务数/已完成数随筛选同步 -->
      <section v-if="deptStats.length || deptFilter !== 'all'">
        <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 mb-3">
          <div class="flex items-baseline gap-2">
            <h2 class="section-title">部门任务完成度</h2>
            <span class="text-xs text-slate-400">{{ deptFilterHint }}</span>
          </div>
          <div class="inline-flex gap-0.5 p-0.5 rounded-lg bg-slate-100">
            <button
              v-for="f in DEPT_FILTERS"
              :key="f.value"
              class="px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-200 ease-out"
              :class="
                deptFilter === f.value
                  ? 'bg-white text-brand-700 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              "
              @click="deptFilter = f.value"
            >
              {{ f.label }}
            </button>
          </div>
        </div>

        <div v-if="!deptStats.length" class="card p-8 text-center text-xs text-slate-500">
          当前筛选条件下暂无任务。
        </div>
        <div
          v-else
          class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 transition-opacity duration-200"
          :class="deptStatsLoading ? 'opacity-50' : ''"
        >
          <div
            v-for="d in deptStats"
            :key="d.deptId"
            class="card p-4"
            :class="d.overdue + d.risk > 0 ? 'border-bad-100' : ''"
          >
            <div class="flex items-center justify-between">
              <span class="text-[13px] font-bold text-slate-800">{{ d.deptName }}</span>
              <span class="text-[11px] text-slate-400">{{ d.total }} 项任务</span>
            </div>
            <div class="mt-3 flex items-baseline gap-1">
              <span class="text-2xl stat-value text-slate-900">{{ d.completion }}%</span>
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
        <h2 class="section-title mb-3">风险与异常</h2>
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

    <!-- 转化概率配置 -->
    <ModalDialog :open="funnelCfgOpen" title="配置各阶段转化概率" width="sm" @close="funnelCfgOpen = false">
      <p class="text-xs text-slate-500 mb-3 leading-relaxed">
        销量预测 = Σ（项目需求 × 所在阶段转化概率）。默认值与阶段百分比一致，保存后全系统共用、立即生效。
      </p>
      <div class="space-y-2.5">
        <div v-for="(item, i) in funnelCfgForm" :key="item.stage" class="flex items-center gap-3">
          <span class="w-40 text-sm text-slate-600">{{ item.stage }}% {{ MARKET_STAGE_LABELS[item.stage] }}</span>
          <input
            v-model.number="funnelCfgForm[i].probPct"
            type="number"
            min="0"
            max="100"
            step="1"
            class="input !w-28 text-right"
            placeholder="0-100"
            title="填写 0 到 100 之间的整数，代表该阶段的转化概率"
          />
          <span class="text-sm text-slate-400">%</span>
        </div>
      </div>
      <p v-if="funnelCfgError" class="mt-3 text-sm text-bad-600">{{ funnelCfgError }}</p>
      <template #footer>
        <button class="btn-ghost" @click="resetFunnelCfg">恢复默认</button>
        <button class="btn-ghost" @click="funnelCfgOpen = false">取消</button>
        <button class="btn-primary" :disabled="funnelCfgSaving" @click="saveFunnelCfg">
          {{ funnelCfgSaving ? '保存中…' : '保存' }}
        </button>
      </template>
    </ModalDialog>

    <!-- 指标下钻 -->
    <ModalDialog :open="!!drill" :title="drill ? `${drill.name} · 趋势` : ''" @close="drill = null">
      <div v-if="drill">
        <div class="flex items-center gap-3 mb-4">
          <span class="chip border" :class="TONE_CHIP[toneOf(drill.tone)]">{{ TONE_LABEL[toneOf(drill.tone)] }}</span>
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
import FunnelChart from '@/components/FunnelChart.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import MonthPicker from '@/components/MonthPicker.vue'
import Sparkline from '@/components/Sparkline.vue'
import { useAuthStore } from '@/stores/auth'
import { useViewStore } from '@/stores/view'
import {
  MARKET_STAGE_LABELS,
  type DeptTaskFilter,
  type DeptTaskStat,
  type Light,
  type MetricRow,
  type OverviewResult,
  type PerfTone,
  type ProjectCompanyBlock,
  type ProjectFunnelResult,
  type SummaryResult,
  type TrendResult,
} from '@/types'
import { fmt, fmtDelta, fmtPct } from '@/utils/format'
import { COLL_TEXT, TONE_BAR, TONE_CHIP, TONE_LABEL, TONE_TEXT, toneOf } from '@/utils/tone'

const view = useViewStore()
const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const error = ref('')
const summary = ref<SummaryResult | null>(null)
const overview = ref<OverviewResult | null>(null)

const drill = ref<MetricRow | null>(null)
const trend = ref<TrendResult | null>(null)
const trendLoading = ref(false)

/** 部门任务完成度的展示口径：全部（默认）/ 本年新增 / 当月新增 / 未结束 */
const DEPT_FILTERS: { value: DeptTaskFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'year', label: '本年新增' },
  { value: 'month', label: '当月新增' },
  { value: 'open', label: '未结束' },
]
const deptFilter = ref<DeptTaskFilter>('all')
const deptStats = ref<DeptTaskStat[]>([])
const deptStatsLoading = ref(false)
const deptFilterHint = computed(
  () =>
    ({
      all: '全量任务，不按时间筛选',
      year: `${(view.period || '').slice(0, 4) || '本年'} 年内创建的任务`,
      month: '所选月份内创建的任务',
      open: '未完成的任务（含进行中与逾期）',
    })[deptFilter.value],
)

const revenueRows = computed(() => (overview.value?.annual ?? []).filter((r) => r.family === 'revenue'))
const simpleRows = computed(() => (overview.value?.annual ?? []).filter((r) => r.family !== 'revenue'))
const snapshotHint = computed(() =>
  (overview.value?.annual ?? []).some((r) => r.snapshot) ? '；运营车辆为期末快照' : '',
)

const toneText = computed(
  () =>
    // 措辞与单指标状态同一套口径（整体结论也是「达成率 ÷ 时间进度」判出来的），
    // 所以文案直接点明与时间进度的关系，避免出现与事实相反的表述
    ({ good: '跑赢时间进度', warn: '略慢于时间进度', bad: '滞后时间进度', none: '暂无数据' })[
      summary.value?.verdict ?? 'none'
    ],
)
/** 总结卡的状态徽章：浅色底 + 深色字，与页面其余卡片同一套配色 */
const toneChip = computed(
  () =>
    ({
      good: 'bg-good-50 text-good-700 border-good-100',
      warn: 'bg-warn-50 text-warn-700 border-warn-100',
      bad: 'bg-bad-50 text-bad-700 border-bad-100',
      none: 'bg-slate-100 text-slate-600 border-slate-200',
    })[summary.value?.verdict ?? 'none'],
)
/** 卡片左侧的语义色条，替代深色卡时代的模糊光晕 */
const toneAccent = computed(
  () =>
    ({
      good: 'bg-good-500',
      warn: 'bg-warn-500',
      bad: 'bg-bad-500',
      none: 'bg-brand-500',
    })[summary.value?.verdict ?? 'none'],
)

const countCards = computed(() => {
  const c = summary.value?.counts
  if (!c) return []
  // 与卡片标签同源（后端按同一套进度状态统计），标签文案也保持一致
  return [
    { label: '已达成', value: c.done, cls: 'text-good-600' },
    { label: '领先', value: c.ahead, cls: 'text-brand-600' },
    { label: '偏慢', value: c.near, cls: 'text-warn-600' },
    { label: '滞后', value: c.risk, cls: 'text-bad-600' },
    { label: '未录入', value: c.none, cls: 'text-slate-400' },
  ]
})

/**
 * 核心指标的状态判定在服务端（`services/achievement.progress_tone`，按「达成率 ÷ 时间进度」），
 * 这里只把接口返回的 tone 映射成样式 —— 样式表在 `@/utils/tone`，
 * 与指标维护页共用同一份，两页不会出现「领先 / 未达标」并存的矛盾。
 */

/** 回款率是卡内次要指标，沿用后端的红黄绿灯判定（它有独立目标），映射到同一套取色 */
function lightTone(light: Light): PerfTone {
  return ({ green: 'done', amber: 'near', red: 'risk', none: 'none' } as Record<string, PerfTone>)[light] ?? 'none'
}

function barWidth(row: MetricRow) {
  const rate = row.rate ?? 0
  return `${Math.min(100, Math.max(2, (rate === Infinity ? 1 : rate) * 100))}%`
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

/**
 * 经营驾驶舱指标下钻趋势的起点月份：固定从 2026-10 起展示，之前的月份不绘图。
 * 10 月为本期汇报起点；如需调整汇报起点（如改为当前月或别的月份），改这里即可。
 */
const TREND_START_PERIOD = '2026-10'

async function openDrilldown(row: MetricRow) {
  drill.value = row
  trend.value = null
  trendLoading.value = true
  try {
    const r = await dashboardApi.trend(row.metricId, view.orgId)
    // 仅保留起点月份及之后的数据点（周期格式 YYYY-MM，字符串比较等价于时间先后）
    trend.value = { ...r, points: r.points.filter((p) => p.period >= TREND_START_PERIOD) }
  } catch {
    trend.value = null
  } finally {
    trendLoading.value = false
  }
}

/** 市场项目概览：三漏斗 + 销量预测（与周期无关，随主加载并发取） */
const funnel = ref<ProjectFunnelResult | null>(null)
/** 市场项目概览的部门筛选：'' = 全部（市场部子树），否则为某二级部门 ID */
const funnelDept = ref<string>('')
/** 二级部门筛选标签：取自漏斗接口返回的 deptOptions，随组织变化同步更新 */
const funnelDeptOptions = computed(() => funnel.value?.deptOptions ?? [])
const funnelDeptName = computed(
  () => funnelDeptOptions.value.find((d) => d.id === funnelDept.value)?.name ?? '',
)
function setFunnelDept(id: string) {
  funnelDept.value = id
  loadFunnel()
}
const probSummary = computed(
  () => (funnel.value?.stages ?? []).map((s) => `${Math.round(s.prob * 100)}%`).join(' / '),
)

/** 转化概率配置弹窗 */
const funnelCfgOpen = ref(false)
const funnelCfgSaving = ref(false)
const funnelCfgError = ref('')
const funnelCfgForm = ref<{ stage: number; probPct: number }[]>([])

function openFunnelConfig() {
  funnelCfgError.value = ''
  funnelCfgForm.value = (funnel.value?.stages ?? []).map((s) => ({
    stage: s.stage,
    probPct: Math.round(s.prob * 100),
  }))
  funnelCfgOpen.value = true
}

/** 恢复默认 = 概率与阶段百分比一致 */
function resetFunnelCfg() {
  funnelCfgForm.value = funnelCfgForm.value.map((item) => ({ ...item, probPct: item.stage }))
}

async function loadFunnel() {
  funnel.value = await dashboardApi.projectFunnel(funnelDept.value || undefined)
}

async function saveFunnelCfg() {
  funnelCfgError.value = ''
  for (const item of funnelCfgForm.value) {
    if (!Number.isFinite(item.probPct) || item.probPct < 0 || item.probPct > 100) {
      funnelCfgError.value = '转化概率应为 0 ~ 100 之间的数字'
      return
    }
  }
  funnelCfgSaving.value = true
  try {
    await dashboardApi.saveFunnelConfig(
      funnelCfgForm.value.map((item) => ({ stage: item.stage as ProjectFunnelResult['stages'][number]['stage'], prob: item.probPct / 100 })),
    )
    await loadFunnel()
    funnelCfgOpen.value = false
  } catch (e) {
    funnelCfgError.value = (e as Error).message
  } finally {
    funnelCfgSaving.value = false
  }
}

/** 部门/班组视角：指标目标只下达在公司与项目公司层级，故无核心指标卡 */
const deptView = computed(() => ['dept', 'team'].includes(overview.value?.orgType ?? ''))

let loadSeq = 0
// 与 loadDeptStats 共用的序号：两边都会写 deptStats，谁发起得晚谁生效，
// 避免「切周期触发的整页刷新」其响应晚于「切筛选触发的局部刷新」时把新数据盖回旧口径
let deptSeq = 0
async function load() {
  if (!view.period || !view.contextReady) return
  const seq = ++loadSeq
  const dseq = ++deptSeq
  loading.value = true
  error.value = ''
  try {
    // 四个请求并发：部门任务完成度 / 市场项目漏斗与总览同源、同权限，一起取不增加往返
    const [s, o, d, f] = await Promise.all([
      dashboardApi.summary(view.period, view.orgId),
      dashboardApi.overview(view.period, view.orgId),
      dashboardApi.deptTaskStats(view.period, deptFilter.value),
      dashboardApi.projectFunnel(funnelDept.value || undefined),
    ])
    // 并发加载时丢弃过期响应，避免先到的 403 覆盖后到的成功结果
    if (seq !== loadSeq) return
    summary.value = s
    overview.value = o
    if (dseq === deptSeq) deptStats.value = d
    funnel.value = f
  } catch (e) {
    if (seq !== loadSeq) return
    error.value = (e as Error).message
    summary.value = null
    overview.value = null
    if (dseq === deptSeq) deptStats.value = []
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

/** 只重取部门任务完成度：切换筛选不必重建整套指标看板 */
async function loadDeptStats() {
  if (!view.period) return
  const seq = ++deptSeq
  deptStatsLoading.value = true
  try {
    const d = await dashboardApi.deptTaskStats(view.period, deptFilter.value)
    if (seq !== deptSeq) return
    deptStats.value = d
  } catch {
    if (seq === deptSeq) deptStats.value = []
  } finally {
    if (seq === deptSeq) deptStatsLoading.value = false
  }
}

watch([() => view.period, () => view.orgId, () => view.contextReady], load, { immediate: true })
watch(deptFilter, loadDeptStats)
</script>
