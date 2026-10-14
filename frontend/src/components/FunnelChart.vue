<template>
  <div class="card p-4">
    <div class="flex items-center justify-between">
      <h3 class="text-[13px] font-bold text-slate-700">{{ title }}</h3>
      <span class="text-[11px] text-slate-400">按累计到达项目计</span>
    </div>
    <div v-if="max <= 0" class="py-10 text-center text-xs text-slate-400">暂无项目数据</div>
    <div v-else class="mt-3 flex items-stretch gap-2.5">
      <!-- 左：漏斗造型（SVG 梯形逐层收窄，末层绿色） -->
      <svg :viewBox="`0 0 ${SVG_W} ${SVG_H}`" class="w-[34%] shrink-0" role="img" :aria-label="title">
        <polygon
          v-for="(layer, i) in layers"
          :key="i"
          :points="layer.points"
          :fill="layer.color"
          class="transition-all duration-300 hover:brightness-110"
        >
          <title>{{ stages[i].label }}：{{ fmt(valueOf(stages[i])) }} {{ unit }}</title>
        </polygon>
      </svg>
      <!-- 右：阶段名 / 数量 / 相对上一层的转化率 -->
      <div class="flex-1 min-w-0 flex flex-col" :style="{ gap: GAP + 'px' }">
        <div
          v-for="(s, i) in stages"
          :key="s.stage"
          class="flex items-center justify-between gap-1.5"
          :style="{ height: LAYER_H + 'px' }"
        >
          <span class="text-xs text-slate-600 truncate" :title="s.label">{{ s.label }}</span>
          <span class="shrink-0 whitespace-nowrap">
            <b class="text-sm text-slate-900">{{ fmt(valueOf(s)) }}</b>
            <span class="text-[11px] text-slate-400 ml-0.5">{{ unit }}</span>
            <span class="text-[11px] text-slate-400 ml-1.5 inline-block w-9 text-right">{{ convText(i) }}</span>
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

const LAYER_H = 26
const GAP = 10
const SVG_W = 200
const SVG_H = computed(() => props.stages.length * LAYER_H + (props.stages.length - 1) * GAP)

/** 浅蓝 → 深蓝，末层（交车/投运）绿色 —— 与设计参考一致 */
const COLORS = ['#DBE8FF', '#BFD6FF', '#93BAFF', '#4D7CFF', '#1F63FF', '#10B981']

const valueOf = (s: FunnelStageStat) => s[props.field]
const max = computed(() => Math.max(0, ...props.stages.map(valueOf)))

/** 各层梯形的四个顶点：上沿接上一层底宽，下沿是本层宽度，居中对齐 */
const layers = computed(() => {
  const cx = SVG_W / 2
  const widths = props.stages.map((s) => {
    if (max.value <= 0) return 0
    // 宽度相对首层（最大值）；设下限保证小值层仍成形
    return Math.max(SVG_W * 0.12, (valueOf(s) / max.value) * SVG_W)
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

/** 相对上一层的转化率（首层 100%）；上一层为 0 时无意义，显示 — */
function convText(i: number): string {
  if (i === 0) return '100%'
  const prev = valueOf(props.stages[i - 1])
  if (prev <= 0) return '—'
  const pct = (valueOf(props.stages[i]) / prev) * 100
  return `${parseFloat(pct.toFixed(1))}%`
}
</script>
