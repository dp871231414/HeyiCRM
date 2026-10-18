<template>
  <section class="card p-5">
    <div class="flex items-baseline gap-2 mb-3">
      <h2 class="section-title">车辆需求分析</h2>
      <span class="text-xs text-slate-400">车头按(车型×电池容量)、挂车按车型汇总总需求数与预估消化数</span>
    </div>

    <!-- 阶段筛选快捷标签：全部 + 各阶段（带转化率后缀，读取漏斗转化率配置） -->
    <div class="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4">
      <span class="text-xs text-slate-400">按阶段筛选</span>
      <div class="inline-flex gap-0.5 p-0.5 rounded-lg bg-slate-100">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-200 ease-out"
          :class="
            selectedStage === t.key
              ? 'bg-white text-brand-700 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          "
          @click="selectedStage = t.key"
        >
          {{ t.label }}<span v-if="t.prob !== null" class="ml-0.5 text-[10px] opacity-70">{{ Math.round(t.prob * 100) }}%</span>
        </button>
      </div>
      <span v-if="selectedStage" class="text-xs text-slate-400">当前：{{ stageLabel(selectedStage) }}</span>
    </div>

    <div v-if="loading" class="py-10 text-center text-sm text-slate-400">加载中…</div>
    <div v-else-if="error" class="py-10 text-center text-sm text-bad-600">{{ error }}</div>
    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- 左：车头需求（按 车型 × 电池容量 组合） -->
      <div class="rounded-xl border border-slate-200 overflow-hidden">
        <div class="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <h3 class="text-[13px] font-bold text-slate-700">车头需求</h3>
          <span class="text-[11px] text-slate-400">{{ tractorRows.length }} 种组合 · 总需求 {{ tractorTotal }} 辆</span>
        </div>
        <div class="max-h-96 overflow-y-auto">
          <table class="w-full text-sm">
            <thead class="sticky top-0 bg-white/95 backdrop-blur text-slate-400 text-[12px]">
              <tr>
                <th class="text-left font-medium px-4 py-2">车辆型号</th>
                <th class="text-left font-medium px-4 py-2">电池容量</th>
                <th class="text-right font-medium px-4 py-2">总需求数(辆)</th>
                <th class="text-right font-medium px-4 py-2">预估消化数量(辆)</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="r in tractorRows" :key="r.model + '|' + r.battery" class="hover:bg-slate-50">
                <td class="px-4 py-2 text-slate-700">{{ r.model }}</td>
                <td class="px-4 py-2 text-slate-500">{{ r.battery }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums text-slate-900">{{ r.qty }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums text-slate-600">{{ fmt(r.digest, 0) }}</td>
              </tr>
              <tr v-if="!tractorRows.length">
                <td colspan="4" class="px-4 py-8 text-center text-xs text-slate-400">该范围暂无车头需求</td>
              </tr>
            </tbody>
            <tfoot v-if="tractorRows.length" class="border-t border-slate-200 bg-slate-50/60">
              <tr>
                <td colspan="2" class="px-4 py-2 text-[12px] font-semibold text-slate-600">合计</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums font-bold text-slate-900">{{ tractorTotal }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums font-bold text-slate-700">{{ fmt(tractorDigestTotal, 1) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <!-- 右：挂车需求（按车型分行，含总数量与预估消化数量） -->
      <div class="rounded-xl border border-slate-200 overflow-hidden">
        <div class="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <h3 class="text-[13px] font-bold text-slate-700">挂车需求</h3>
          <span class="text-[11px] text-slate-400">{{ trailerRows.length }} 种车型</span>
        </div>
        <div class="max-h-96 overflow-y-auto">
          <table class="w-full text-sm">
            <thead class="sticky top-0 bg-white/95 backdrop-blur text-slate-400 text-[12px]">
              <tr>
                <th class="text-left font-medium px-4 py-2">挂车型号</th>
                <th class="text-right font-medium px-4 py-2">总需求数(辆)</th>
                <th class="text-right font-medium px-4 py-2">预估消化数量(辆)</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="r in trailerRows" :key="r.model" class="hover:bg-slate-50">
                <td class="px-4 py-2 text-slate-700">{{ r.model }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums text-slate-900">{{ r.qty }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums text-slate-600">{{ fmt(r.digest, 0) }}</td>
              </tr>
              <tr v-if="!trailerRows.length">
                <td colspan="3" class="px-4 py-8 text-center text-xs text-slate-400">该范围暂无挂车需求</td>
              </tr>
            </tbody>
            <tfoot v-if="trailerRows.length" class="border-t border-slate-200 bg-slate-50/60">
              <tr>
                <td class="px-4 py-2 text-[12px] font-semibold text-slate-600">合计</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums font-bold text-slate-900">{{ trailerQtyTotal }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums font-bold text-slate-700">{{ fmt(trailerDigestTotal, 1) }}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { dashboardApi } from '@/api'
import type { DemandAnalysisResult, DemandStageMeta, DemandTractorRow, DemandTrailerRow } from '@/types'
import { fmt } from '@/utils/format'

const props = defineProps<{ dept?: string }>()

const data = ref<DemandAnalysisResult | null>(null)
const loading = ref(false)
const error = ref('')
const selectedStage = ref<string>('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await dashboardApi.demandAnalysis(props.dept || undefined)
    // 切换部门后重置为「全部」，避免停留在某部门不存在的阶段上
    selectedStage.value = ''
  } catch (e) {
    error.value = (e as Error).message
    data.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.dept, load, { immediate: true })

/** 筛选标签：全部 + 各阶段（带转化率后缀）。全部无后缀、默认选中 */
const tabs = computed(() => {
  const stages: DemandStageMeta[] = data.value?.stages ?? []
  return [
    { key: '', label: '全部', prob: null as number | null },
    ...stages.map((s) => ({ key: String(s.stage), label: s.label, prob: s.prob })),
  ]
})

function stageLabel(key: string): string {
  return tabs.value.find((t) => t.key === key)?.label ?? key
}

const tractorRows = computed<DemandTractorRow[]>(() => {
  const t = data.value?.tractor
  if (!t) return []
  return selectedStage.value ? (t.byStage[selectedStage.value] ?? []) : t.all
})

const trailerRows = computed<DemandTrailerRow[]>(() => {
  const t = data.value?.trailer
  if (!t) return []
  return selectedStage.value ? (t.byStage[selectedStage.value] ?? []) : t.all
})

const tractorTotal = computed(() => tractorRows.value.reduce((a, r) => a + r.qty, 0))
const tractorDigestTotal = computed(
  () => Math.round(tractorRows.value.reduce((a, r) => a + (r.digest || 0), 0)),
)
const trailerQtyTotal = computed(() => trailerRows.value.reduce((a, r) => a + r.qty, 0))
const trailerDigestTotal = computed(
  () => Math.round(trailerRows.value.reduce((a, r) => a + r.digest, 0)),
)
</script>
