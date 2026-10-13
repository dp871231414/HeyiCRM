import type { PerfTone } from '@/types'

/**
 * 进度状态（tone）的展示映射 —— 全系统唯一一份。
 *
 * 判定在服务端（`services/achievement.progress_tone`，按「达成率 ÷ 时间进度」分档），
 * 这里只负责「取什么样式」。经营驾驶舱与指标维护共用本模块，
 * 避免两个页面各写一套标签/配色而出现同一指标「领先 / 未达标」并存的矛盾。
 *
 * 注意区分两个概念：
 *   · tone    —— 单个指标的**进度状态**（done / ahead / near / risk / none），本模块处理；
 *   · verdict —— 整体经营**结论**（good / warn / bad / none），见 `summary.verdict`。
 */

export const TONE_LABEL: Record<PerfTone, string> = {
  done: '已达成',
  ahead: '领先',
  near: '偏慢',
  risk: '滞后',
  none: '未录入',
}

/** 徽章：浅底 + 深字 + 同色描边 */
export const TONE_CHIP: Record<PerfTone, string> = {
  done: 'bg-good-50 text-good-700 border-good-100',
  ahead: 'bg-brand-50 text-brand-700 border-brand-100',
  near: 'bg-warn-50 text-warn-700 border-warn-100',
  risk: 'bg-bad-50 text-bad-700 border-bad-100',
  none: 'bg-slate-100 text-slate-500 border-slate-200',
}

/** 强调文字（达成率数值、完成率等） */
export const TONE_TEXT: Record<PerfTone, string> = {
  done: 'text-good-600',
  ahead: 'text-brand-600',
  near: 'text-warn-600',
  risk: 'text-bad-600',
  none: 'text-slate-400',
}

/** 进度条填充 */
export const TONE_BAR: Record<PerfTone, string> = {
  done: 'bg-good-500',
  ahead: 'bg-brand-500',
  near: 'bg-warn-500',
  risk: 'bg-bad-500',
  none: 'bg-slate-300',
}

/** 圆点（用于列表/图例） */
export const TONE_DOT: Record<PerfTone, string> = {
  done: 'bg-good-500',
  ahead: 'bg-brand-500',
  near: 'bg-warn-500',
  risk: 'bg-bad-500',
  none: 'bg-slate-300',
}

/** 兜底：接口未返回或值未知时按「未录入」处理，避免样式取到 undefined */
export function toneOf(value: string | null | undefined): PerfTone {
  return (['done', 'ahead', 'near', 'risk', 'none'] as const).includes(value as PerfTone)
    ? (value as PerfTone)
    : 'none'
}

/**
 * 回款率的数值颜色 —— 它是「卡内的第二个指标」，有自己的目标（默认 95%），
 * 与指标的进度状态不是一回事。若一直着色，同一张卡会出现两种色相；
 * 因此**达标时用中性深灰**，仅未达目标时提示（黄 / 红）。
 * 两个页面共用，保证同一子指标在任何页面观感一致。
 */
export const COLL_TEXT: Record<PerfTone, string> = {
  done: 'text-slate-600',
  ahead: 'text-slate-600',
  near: 'text-warn-600',
  risk: 'text-bad-600',
  none: 'text-slate-400',
}
