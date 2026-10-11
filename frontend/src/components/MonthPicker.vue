<template>
  <label class="inline-flex items-center gap-1.5 text-xs text-slate-500">
    统计周期
    <input
      type="month"
      class="input !py-1.5 !px-2 !w-auto text-xs font-semibold"
      :min="MIN_PERIOD"
      :max="MAX_PERIOD"
      :value="modelValue"
      :title="`可选范围：${MIN_PERIOD} 至 ${MAX_PERIOD}`"
      @change="onChange"
    />
  </label>
</template>

<script setup lang="ts">
import { MONTH_MIN, MONTH_MAX } from '@/constants/period'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const MIN_PERIOD = MONTH_MIN
const MAX_PERIOD = MONTH_MAX

/** 归一到 [min,max]：浏览器对 type=month 的键盘输入不保证受限，这里兜一道 */
function clamp(v: string): string {
  if (!/^\d{4}-\d{2}$/.test(v)) return MIN_PERIOD
  if (v < MIN_PERIOD) return MIN_PERIOD
  if (v > MAX_PERIOD) return MAX_PERIOD
  return v
}

function onChange(e: Event) {
  const next = clamp((e.target as HTMLInputElement).value)
  const el = e.target as HTMLInputElement
  if (el.value !== next) el.value = next
  if (next !== props.modelValue) emit('update:modelValue', next)
}
</script>
