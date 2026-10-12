<template>
  <div ref="rootRef" class="relative inline-block">
    <!-- 触发器 -->
    <button
      ref="triggerRef"
      type="button"
      class="inline-flex items-center gap-2 rounded-lg border bg-white px-3 py-1.5 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-brand-100"
      :class="
        open
          ? 'border-brand-400 text-brand-700 ring-2 ring-brand-100'
          : 'border-slate-200 text-slate-700 hover:border-brand-300 hover:bg-brand-50/40'
      "
      aria-haspopup="dialog"
      :aria-expanded="open"
      :title="`统计周期（可选 ${MONTH_MIN} 至 ${MONTH_MAX}）`"
      @click="toggle"
      @keydown.down.prevent="openPanel"
    >
      <svg class="h-3.5 w-3.5 text-brand-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="4.5" width="18" height="16" rx="2.5" />
        <path d="M3 9.5h18M8 2.5v4M16 2.5v4" stroke-linecap="round" />
      </svg>
      <span class="tabular-nums">{{ label }}</span>
      <svg
        class="h-3 w-3 text-slate-400 transition-transform duration-150"
        :class="open && 'rotate-180'"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
      >
        <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <!-- 面板 -->
    <div
      v-if="open"
      ref="panelRef"
      role="dialog"
      aria-label="选择统计周期"
      tabindex="-1"
      class="absolute left-0 z-50 mt-2 w-[252px] rounded-xl border border-slate-200 bg-white p-3 shadow-pop outline-none"
    >
      <!-- 头部：左右翻页 + 年 / 年段切换 -->
      <div class="mb-2 flex items-center justify-between">
        <button type="button" class="picker-nav" :disabled="!canPrev" aria-label="上一页" @click="step(-1)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="h-3.5 w-3.5">
            <path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>

        <button
          type="button"
          class="rounded-md px-2.5 py-1 text-xs font-bold text-slate-800 transition hover:bg-slate-100"
          :title="mode === 'month' ? '点击选择年份' : '点击返回月份'"
          @click="toggleMode"
        >
          <span class="tabular-nums">{{ mode === 'month' ? `${viewYear}年` : yearRangeLabel }}</span>
        </button>

        <button type="button" class="picker-nav" :disabled="!canNext" aria-label="下一页" @click="step(1)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="h-3.5 w-3.5">
            <path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>

      <!-- 月份网格 -->
      <div v-if="mode === 'month'" class="grid grid-cols-3 gap-1.5">
        <button
          v-for="m in 12"
          :key="m"
          type="button"
          class="h-9 rounded-lg text-xs transition"
          :class="monthClass(viewYear, m)"
          :disabled="!inRange(viewYear, m)"
          :aria-pressed="monthValue(viewYear, m) === modelValue"
          @click="selectMonth(viewYear, m)"
        >
          {{ m }}月
        </button>
      </div>

      <!-- 年份网格（跨 12 年翻页，避免逐年点到 2099） -->
      <div v-else class="grid grid-cols-3 gap-1.5">
        <button
          v-for="y in yearCells"
          :key="y"
          type="button"
          class="h-9 rounded-lg text-xs transition"
          :class="yearClass(y)"
          :disabled="y < MIN_Y || y > MAX_Y"
          :aria-pressed="y === selectedYear"
          @click="selectYear(y)"
        >
          {{ y }}
        </button>
      </div>

      <p class="mt-2.5 border-t border-slate-100 pt-2 text-[11px] text-slate-400">
        可选范围 <span class="tabular-nums">{{ MONTH_MIN }}</span> ~
        <span class="tabular-nums">{{ MONTH_MAX }}</span>
        <span v-if="mode === 'month'" class="text-slate-300"> · 点年份可快速跳转</span>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { MONTH_MAX, MONTH_MIN } from '@/constants/period'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const rootRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLButtonElement | null>(null)

const open = ref(false)
/** 面板的模式：先选月，点年份标题后切到选年（参考主流月份选择器） */
const mode = ref<'month' | 'year'>('month')

const MIN_Y = Number(MONTH_MIN.slice(0, 4))
const MAX_Y = Number(MONTH_MAX.slice(0, 4))
/** 年份网格每页 12 个，页起点与下界对齐，最后两页会包含越界年份（禁用） */
const YEARS_PER_PAGE = 12

function monthValue(y: number, m: number) {
  return `${y}-${String(m).padStart(2, '0')}`
}

function inRange(y: number, m: number) {
  const v = monthValue(y, m)
  return v >= MONTH_MIN && v <= MONTH_MAX
}

const selectedYear = computed(() => Number(props.modelValue.slice(0, 4)))
const selectedMonth = computed(() => Number(props.modelValue.slice(5, 7)))

/** 面板正在浏览的年份，与选中值解耦：翻页不应立刻改选中值 */
const viewYear = ref(Number(props.modelValue.slice(0, 4)) || MIN_Y)
/** 年份网格当前页起点 */
const pageStart = ref(MIN_Y)

const label = computed(() => {
  const y = selectedYear.value
  const m = selectedMonth.value
  return Number.isFinite(y) && Number.isFinite(m) && m >= 1 && m <= 12 ? `${y}年${m}月` : '—'
})

const yearRangeLabel = computed(() => `${pageStart.value}-${pageStart.value + YEARS_PER_PAGE - 1}`)
const yearCells = computed(() => Array.from({ length: YEARS_PER_PAGE }, (_, i) => pageStart.value + i))

const canPrev = computed(() =>
  mode.value === 'month' ? viewYear.value > MIN_Y : pageStart.value > MIN_Y,
)
const canNext = computed(() =>
  mode.value === 'month' ? viewYear.value < MAX_Y : pageStart.value + YEARS_PER_PAGE <= MAX_Y,
)

/** 本机当前月，用于「本月」标记；不在可选范围内则不标记 */
const todayPeriod = (() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
})()

function monthClass(y: number, m: number) {
  const v = monthValue(y, m)
  if (!inRange(y, m)) return 'text-slate-300 cursor-not-allowed'
  if (v === props.modelValue) return 'bg-brand-600 font-semibold text-white shadow-sm'
  if (v === todayPeriod) return 'font-semibold text-brand-600 ring-1 ring-inset ring-brand-200 hover:bg-brand-50'
  return 'text-slate-600 hover:bg-brand-50 hover:text-brand-700'
}

function yearClass(y: number) {
  if (y < MIN_Y || y > MAX_Y) return 'text-slate-300 cursor-not-allowed'
  if (y === selectedYear.value) return 'bg-brand-600 font-semibold text-white shadow-sm'
  if (y === viewYear.value) return 'font-semibold text-brand-600 ring-1 ring-inset ring-brand-200 hover:bg-brand-50'
  return 'text-slate-600 hover:bg-brand-50 hover:text-brand-700'
}

function step(dir: number) {
  if (mode.value === 'month') {
    const next = viewYear.value + dir
    if (next < MIN_Y || next > MAX_Y) return
    viewYear.value = next
  } else {
    // 页起点按 12 年对齐到下界，最后一页可能含越界年份（按钮已禁用）
    const next = pageStart.value + dir * YEARS_PER_PAGE
    if (next >= MIN_Y && next <= MAX_Y) pageStart.value = next
  }
}

function toggleMode() {
  if (mode.value === 'month') {
    pageStart.value = MIN_Y + Math.floor((viewYear.value - MIN_Y) / YEARS_PER_PAGE) * YEARS_PER_PAGE
    mode.value = 'year'
  } else {
    mode.value = 'month'
  }
}

function selectYear(y: number) {
  viewYear.value = y
  mode.value = 'month'
}

function selectMonth(y: number, m: number) {
  if (!inRange(y, m)) return
  const v = monthValue(y, m)
  if (v !== props.modelValue) emit('update:modelValue', v)
  close(true)
}

function openPanel() {
  viewYear.value = Number.isFinite(selectedYear.value) ? selectedYear.value : MIN_Y
  mode.value = 'month'
  open.value = true
  nextTick(() => panelRef.value?.focus())
}

function close(returnFocus: boolean) {
  open.value = false
  if (returnFocus) triggerRef.value?.focus()
}

function toggle() {
  open.value ? close(false) : openPanel()
}

function onDocDown(e: MouseEvent) {
  if (!open.value) return
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) close(false)
}

function onDocKey(e: KeyboardEvent) {
  if (!open.value) return
  if (e.key === 'Escape') {
    e.preventDefault()
    close(true)
  }
}

onMounted(() => {
  document.addEventListener('mousedown', onDocDown)
  document.addEventListener('keydown', onDocKey)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocDown)
  document.removeEventListener('keydown', onDocKey)
})
</script>
