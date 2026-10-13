import type { Light } from '@/types'

/** 数值格式化：空值显示「—」 */
export function fmt(value: number | null | undefined, digits?: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const d = digits ?? (Number.isInteger(value) ? 0 : 2)
  return Number(value).toFixed(d)
}

/** 比率格式化 */
export function fmtPct(rate: number | null | undefined, digits = 1): string {
  if (rate === null || rate === undefined || Number.isNaN(rate)) return '—'
  if (rate === Infinity) return '∞'
  return `${(rate * 100).toFixed(digits)}%`
}

/** 带正负号的百分点 */
export function fmtDelta(delta: number | null | undefined, digits = 1): string {
  if (delta === null || delta === undefined || Number.isNaN(delta)) return '—'
  const sign = delta >= 0 ? '+' : ''
  return `${sign}${(delta * 100).toFixed(digits)}pp`
}

/**
 * 目标达成判定（`light`）的展示文案。
 *
 * 注意：**指标的界面状态请用 `@/utils/tone`**（按「达成率 ÷ 时间进度」分档，
 * 与后端 progress_tone 同源）。这里的 light 是「实际 vs 目标」的判定，
 * 年度目标未走完时恒为「未达标」，只在回款率等有独立目标的子指标上使用。
 */
export const LIGHT_LABEL: Record<Light, string> = {
  green: '达标',
  amber: '接近目标',
  red: '未达标',
  none: '未录入',
}

export const LIGHT_CLASS: Record<Light, string> = {
  green: 'bg-good-50 text-good-700 border-good-100',
  amber: 'bg-warn-50 text-warn-700 border-warn-100',
  red: 'bg-bad-50 text-bad-700 border-bad-100',
  none: 'bg-slate-100 text-slate-500 border-slate-200',
}

export const LIGHT_DOT: Record<Light, string> = {
  green: 'bg-good-500',
  amber: 'bg-warn-500',
  red: 'bg-bad-500',
  none: 'bg-slate-300',
}

export const STATUS_CLASS: Record<string, string> = {
  done: 'bg-good-50 text-good-700 border-good-100',
  normal: 'bg-brand-50 text-brand-700 border-brand-100',
  due_soon: 'bg-warn-50 text-warn-700 border-warn-100',
  overdue: 'bg-bad-50 text-bad-700 border-bad-100',
  risk: 'bg-bad-50 text-bad-700 border-bad-100',
}
