/**
 * 驾驶舱「AI 经营点评」的两级调用通道。
 *
 * 通道顺序（先用快的，失败再退化）：
 *   1. 自定义模型 —— 走后端代理 `/ai/insight`，Key 只在服务端，实测约 1~2s。
 *   2. 云服务 auto —— WorkBuddy 免密钥大模型，实测推理型模型约 80s，仅作兜底。
 *
 * 两条通道都失败时抛错，由调用方降级为规则化分析。
 *
 * 为什么不把自定义模型的 Key 放在前端：浏览器产物与 DevTools 都能看到明文，
 * 等同于公开 Key。自定义模型支持 OpenAI 兼容协议，由后端统一代理是唯一稳妥做法。
 */
import { createWorkBuddyCloud } from '@tencent-ai/workbuddy-cloud-sdk'

import { aiApi } from '@/api'

const PUBLIC_CONFIG = {
  endpoint: 'https://heyi-fleet-dashboard.app.workbuddy.host',
  oauthRelayBaseUrl: 'https://www.workbuddy.cn/v2/as/genie-baas/oauth',
  publishableKey: 'wbpk_qceQci7k713KUpJUCItWaO_7EMlM42ZXBs9razwDwKOOExkREaszZNs',
}

/** 云服务客户端（全局单例，仅兜底通道使用） */
const cloud = createWorkBuddyCloud(PUBLIC_CONFIG)

/** 单条通道的超时上限（ms）。超时后主动放弃该通道，避免无限等待。 */
const CUSTOM_TIMEOUT_MS = 30_000
const CLOUD_TIMEOUT_MS = 45_000

/** 本次调用命中的通道，供界面标注来源 */
export type InsightSource = 'custom' | 'cloud'

export interface InsightResult {
  text: string
  source: InsightSource
}

/**
 * 给 Promise 加超时。超时后 reject，走下一条通道。
 * 注意：超时不会真的中断底层 fetch（SSE 已建立），但能让 UI 及时给出反馈。
 */
function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label}超时（>${ms / 1000}s）`)), ms)
    p.then(
      (v) => {
        clearTimeout(timer)
        resolve(v)
      },
      (e) => {
        clearTimeout(timer)
        reject(e)
      },
    )
  })
}

/** 通道 1：自定义模型（后端代理） */
async function viaCustomModel(context: string): Promise<string> {
  const data = await withTimeout(aiApi.insight(context), CUSTOM_TIMEOUT_MS, '自定义模型')
  const text = (data?.text ?? '').trim()
  if (!text) throw new Error('自定义模型返回空内容')
  return text
}

/** 通道 2：云服务 auto（兜底） */
async function viaCloudService(context: string): Promise<string> {
  const models = await cloud.llm.models.list()
  const model = models.find((m) => m.enabled)
  if (!model) throw new Error('暂无可用的大模型')

  let answer = ''
  const stream = (async () => {
    for await (const chunk of cloud.llm.chat.completions.create({
      model: model.id,
      messages: [
        {
          role: 'system',
          content:
            '你是「合一重卡生态经营看板」的经营分析助手。请基于输入的经营数据，用简洁、客观的中文给出 2~3 句经营点评：先点出最值得关注的一项，再给出一条可执行的建议。只依据输入数据，不要编造数字。',
        },
        { role: 'user', content: context },
      ],
      stream: true,
    })) {
      const delta = chunk.choices?.[0]?.delta?.content
      if (delta) answer += delta
    }
  })()

  await withTimeout(stream, CLOUD_TIMEOUT_MS, '云服务')
  const text = answer.trim()
  if (!text) throw new Error('云服务返回空内容')
  return text
}

/**
 * 生成经营点评：自定义模型优先，失败自动回退云服务。
 * 两条通道都失败则抛出最后一个错误，由调用方展示规则化分析。
 */
export async function generateInsight(context: string): Promise<InsightResult> {
  if (!context.trim()) throw new Error('经营数据上下文为空')

  try {
    return { text: await viaCustomModel(context), source: 'custom' }
  } catch (customErr) {
    console.warn('[AI] 自定义模型通道失败，回退云服务：', customErr)
  }

  const text = await viaCloudService(context)
  return { text, source: 'cloud' }
}
