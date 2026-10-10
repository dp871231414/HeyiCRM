<template>
  <svg :viewBox="`0 0 ${w} ${h}`" class="w-full" :style="{ height: height + 'px' }" preserveAspectRatio="none">
    <defs>
      <linearGradient :id="gid" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity="0.28" />
        <stop offset="100%" :stop-color="color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path v-if="area" :d="areaPath" :fill="`url(#${gid})`" />
    <path :d="linePath" fill="none" :stroke="color" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
    <circle v-for="(p, i) in pts" :key="i" :cx="p.x" :cy="p.y" r="2.6" :fill="color" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ values: number[]; color?: string; height?: number; area?: boolean }>(), {
  color: '#4F46E5',
  height: 120,
  area: true,
})

const w = 600
const h = computed(() => props.height)
const gid = `spark-${Math.random().toString(36).slice(2, 8)}`

const pts = computed(() => {
  const vs = props.values
  if (!vs.length) return []
  const h = props.height
  const min = Math.min(...vs)
  const max = Math.max(...vs)
  const span = max - min || 1
  const step = vs.length > 1 ? w / (vs.length - 1) : 0
  return vs.map((v, i) => ({ x: i * step, y: h - 8 - ((v - min) / span) * (h - 20) }))
})

const linePath = computed(() => pts.value.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '))
const areaPath = computed(() =>
  pts.value.length ? `${linePath.value} L${pts.value[pts.value.length - 1].x},${props.height} L0,${props.height} Z` : '',
)
</script>
