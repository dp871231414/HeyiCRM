/**
 * 统计周期的可选范围（唯一口径来源）。
 *
 * 业务约定：统计周期按月份维护，可选范围自 2026-09 起、向后逐月，
 * 上限到 2099-12。默认选中「当前周期」，若超出范围则收敛到范围内。
 */

export const MONTH_MIN = '2026-09'
export const MONTH_MAX = '2099-12'

/** 校验并归一到可选范围内；非法输入回落到下界 */
export function clampMonth(value: string): string {
  if (!/^\d{4}-\d{2}$/.test(value || '')) return MONTH_MIN
  if (value < MONTH_MIN) return MONTH_MIN
  if (value > MONTH_MAX) return MONTH_MAX
  return value
}

/** 枚举可选范围内的全部月份（含首尾），升序 */
export function listMonths(): string[] {
  const out: string[] = []
  let y = Number(MONTH_MIN.slice(0, 4))
  let m = Number(MONTH_MIN.slice(5, 7))
  const endY = Number(MONTH_MAX.slice(0, 4))
  const endM = Number(MONTH_MAX.slice(5, 7))
  while (y < endY || (y === endY && m <= endM)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`)
    m += 1
    if (m > 12) {
      m = 1
      y += 1
    }
  }
  return out
}
