<template>
  <div class="card p-4">
    <div class="flex items-center justify-between gap-2">
      <h3 class="whitespace-nowrap text-[14px] font-bold text-slate-700">{{ title }}</h3>
      <span class="whitespace-nowrap text-[11px] text-slate-400">按阶段当前数量计</span>
    </div>
    <div v-if="total <= 0" class="py-10 text-center text-xs text-slate-400">暂无项目数据</div>
    <div v-else class="mt-3 flex items-stretch gap-3">
      <!-- 左：放大漏斗（SVG 只画梯形、允许拉伸铺满固定高度；阶段标题用 HTML 绝对定位叠在对应层中心，像素级对齐） -->
      <div class="relative w-[56%] shrink-0" :style="{ height: FUNNEL_H + 'px' }">
        <svg
          :viewBox="`0 0 ${SVG_W} ${SVG_H}`"
          preserveAspectRatio="none"
          class="absolute inset-0 h-full w-full"
          role="img"
          :aria-label="title"
        >
          <polygon
            v-for="(layer, i) in layers"
            :key="'p' + i"
            :points="layer.points"
            :fill="layer.color"
            class="transition-all duration-300 hover:brightness-110"
          >
            <title>{{ stages[i].label }}：{{ fmt(valueOf(stages[i])) }} {{ unit }}</title>
          </polygon>
        </svg>
        <span
          v-for="(s, i) in stages"
          :key="'t' + i"
          class="funnel-label pointer-events-none absolute left-1/2 whitespace-nowrap text-[13px] font-semibold"
          :style="{ top: layerCenterPct(i) * 100 + '%', color: TEXT_COLORS[i], transform: 'translate(-50%, -50%)' }"
        >{{ s.label }}</span>
      </div>
      <!-- 右：各阶段当前数量 + 占该指标总量的百分比（行高与漏斗层一致，逐层对齐） -->
      <div class="flex-1 min-w-0 flex flex-col" :style="{ gap: GAP + 'px' }">
        <div
          v-for="s in stages"
          :key="s.stage"
          class="flex items-center justify-end gap-1.5"
          :style="{ height: LAYER_H + 'px' }"
        >
          <b class="text-lg text-slate-900 tabular-nums leading-none">{{ fmt(valueOf(s)) }}</b>
          <span class="text-[11px] text-slate-400">{{ unit }}</span>
          <span class="pct text-[12px] text-slate-500 w-12 text-right tabular-nums leading-none">{{ pctOf(s) }}</span>
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

/** 漏斗放大：每层 46px、层间距 10px，六层总高 326px（旧版仅 ~244px） */
const LAYER_H = 46
const GAP = 10
const SVG_W = 220
const SVG_H = computed(() => props.stages.length * LAYER_H + (props.stages.length - 1) * GAP)
const FUNNEL_H = computed(() => SVG_H.value)

/** 浅蓝 → 深蓝，末层（交车/投运）绿色 —— 与设计参考一致 */
const COLORS = ['#DBE8FF', '#BFD6FF', '#93BAFF', '#4D7CFF', '#1F63FF', '#10B981']
/** 浅色层用深蓝字、深色层用白字，保证标题可读 */
const TEXT_COLORS = ['#1E3A8A', '#1E3A8A', '#1E40AF', '#FFFFFF', '#FFFFFF', '#FFFFFF']

const valueOf = (s: FunnelStageStat) => s[props.field]
const max = computed(() => Math.max(0, ...props.stages.map(valueOf)))
const total = computed(() => props.stages.reduce((a, s) => a + valueOf(s), 0))

/** 第 i 层中心在漏斗总高中的比例（供 HTML 标题定位） */
function layerCenterPct(i: number): number {
  return (i * (LAYER_H + GAP) + LAYER_H / 2) / SVG_H.value
}

/** 各层梯形顶点：宽度按当前阶段数值占最大值的比例（设下限保证小值层仍成形），上沿接上一层底宽 */
const layers = computed(() => {
  const cx = SVG_W / 2
  const widths = props.stages.map((s) => {
    if (max.value <= 0) return 0
    return Math.max(SVG_W * 0.3, (valueOf(s) / max.value) * SVG_W)
  })
  return props.stages.map((_, i) => {
    const topW = i === 0 ? widths[0] : widths[i - 1]
    const botW = widths[i]
    const y0 = i * (LAYER_H + GAP)
    const y1 = y0 + LAYER_H
    return {
      points: `${cx - topW / 2},${y0} ${cx + topW / 2},${y0} ${cx + botW / 2},${y1} ${cx - botW / 2},${y1}`,
      color: COLORS[i] ?? COLORS[COLORS.length - 1],
    }
  })
})

/** 该层当前数量占「该指标总量」的百分比（如 8 个 / 共 30 个 = 26.7%） */
function pctOf(s: FunnelStageStat): string {
  if (total.value <= 0) return '0%'
  const p = (valueOf(s) / total.value) * 100
  return `${Math.round(p * 10) / 10}%`
}
</script>
