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
