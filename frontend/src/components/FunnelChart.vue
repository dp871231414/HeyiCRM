<template>
  <div class="card p-4">
    <div class="flex items-center justify-between">
      <h3 class="text-[13px] font-bold text-slate-700">{{ title }}</h3>
      <span class="text-[11px] text-slate-400">累计口径</span>
    </div>
    <div v-if="max <= 0" class="py-10 text-center text-xs text-slate-400">暂无项目数据</div>
    <div v-else class="mt-3 space-y-1.5">
      <div v-for="(s, i) in stages" :key="s.stage" class="group">
        <div
          class="mx-auto h-9 rounded-md flex items-center justify-center transition-all duration-300 group-hover:brightness-110"
          :class="BAR_COLORS[i]"
          :style="{ width: barWidth(valueOf(s)) }"
        >
          <span class="text-xs font-extrabold text-white drop-shadow-sm whitespace-nowrap px-1">
            {{ fmt(valueOf(s)) }} {{ unit }}
          </span>
        </div>
        <div class="mt-0.5 text-center text-[11px] text-slate-500">
          {{ s.stage }}% {{ s.label }}
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

/** 自上而下由浅入深的 brand 色阶，强化漏斗的层级感 */
const BAR_COLORS = [
  'bg-brand-300',
  'bg-brand-400',
  'bg-brand-500',
  'bg-brand-600',
  'bg-brand-700',
  'bg-brand-800',
]

const valueOf = (s: FunnelStageStat) => s[props.field]
const max = computed(() => Math.max(0, ...props.stages.map(valueOf)))

/** 相对首层（最大值）的宽度百分比；设下限保证小值层仍可见可读 */
function barWidth(v: number): string {
  if (max.value <= 0) return '0%'
  const pct = Math.max(14, Math.round((v / max.value) * 100))
  return `${pct}%`
}
</script>
