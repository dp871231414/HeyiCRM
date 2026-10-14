<template>
  <div class="card p-4">
    <div class="flex items-center justify-between gap-2">
      <h3 class="whitespace-nowrap text-[14px] font-bold text-slate-700">{{ title }}</h3>
      <span class="whitespace-nowrap text-[11px] text-slate-400">按阶段当前数量计</span>
    </div>
    <div v-if="total <= 0" class="py-8 text-center text-xs text-slate-400">暂无项目数据</div>
    <div v-else class="mt-3 flex items-stretch gap-4">
      <!-- 左：条形图（矩形，按层级排列，左对齐，宽度反映当前阶段数值） -->
      <div class="flex w-[27%] shrink-0 flex-col" :style="{ gap: GAP + 'px' }">
        <div
          v-for="(s, i) in stages"
          :key="'bar' + i"
          class="funnel-bar rounded-sm transition-all duration-300 hover:brightness-110"
          :style="{
            height: BAR_H + 'px',
            width: barW(s) + '%',
            background: COLORS[i] ?? COLORS[COLORS.length - 1],
          }"
        >
          <title>{{ s.label }}：{{ fmt(valueOf(s)) }} {{ unit }}</title>
        </div>
      </div>
      <!-- 右：阶段标题 + 当前数量 + 占比，按层级排列，与左条形逐层对齐 -->
      <div class="flex min-w-0 flex-1 flex-col" :style="{ gap: GAP + 'px' }">
        <div
          v-for="(s, i) in stages"
          :key="'row' + i"
          class="flex items-center justify-between gap-1.5"
          :style="{ height: BAR_H + 'px' }"
        >
          <span class="funnel-stage-label truncate text-[12px] font-medium text-slate-700">{{ s.label }}</span>
          <span class="flex shrink-0 items-center gap-1.5">
            <b class="text-[15px] tabular-nums leading-none text-slate-900">{{ fmt(valueOf(s)) }}</b>
            <span class="text-[10px] text-slate-400">{{ unit }}</span>
            <span class="pct w-11 text-right text-[11px] tabular-nums leading-none text-slate-500">{{ pctOf(s) }}</span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { FunnelStageStat } from '@/types'
import { fmt } from '@/utils/format'

const props = defineProps<{
  title: string
  stages: FunnelStageStat[]
  /** 每层取哪个数值字段：项目数 / 牵引车需求 / 挂车需求 */
  field: 'count' | 'tractor' | 'trailer'
  unit: string
}>()

/** 缩小整体卡片高度：每层 34px、层间距 6px（旧版 46px / 10px） */
const BAR_H = 34
const GAP = 6

/** 浅蓝 → 深蓝，末层（交车/投运）绿色 —— 与设计参考一致 */
const COLORS = ['#DBE8FF', '#BFD6FF', '#93BAFF', '#4D7CFF', '#1F63FF', '#10B981']

const valueOf = (s: FunnelStageStat) => s[props.field]
const max = computed(() => Math.max(0, ...props.stages.map(valueOf)))
const total = computed(() => props.stages.reduce((a, s) => a + valueOf(s), 0))

/** 条形宽度：当前阶段数值占最大值的比例；设下限保证小值层仍成形 */
function barW(s: FunnelStageStat): number {
  if (max.value <= 0) return 0
  return Math.max(8, (valueOf(s) / max.value) * 100)
}

/** 该层当前数量占「该指标总量」的百分比（如 8 个 / 共 30 个 = 26.7%） */
function pctOf(s: FunnelStageStat): string {
  if (total.value <= 0) return '0%'
  const p = (valueOf(s) / total.value) * 100
  return `${Math.round(p * 10) / 10}%`
}
</script>
