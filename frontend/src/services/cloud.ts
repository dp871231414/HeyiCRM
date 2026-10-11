/**
 * WorkBuddy 云服务接入（LLM 模块 · 免密钥大模型）。
 *
 * publicConfig 由 workbuddy_cloud_service 激活时返回，是唯一可下发给前端运行时的值；
 * 应用复用了同一个 applicationId，发布域名固定，因此这里按激活结果写入即可。
 */
import { createWorkBuddyCloud } from '@tencent-ai/workbuddy-cloud-sdk'

const PUBLIC_CONFIG = {
  endpoint: 'https://heyi-fleet-dashboard.app.workbuddy.host',
  oauthRelayBaseUrl: 'https://www.workbuddy.cn/v2/as/genie-baas/oauth',
  publishableKey: 'wbpk_qceQci7k713KUpJUCItWaO_7EMlM42ZXBs9razwDwKOOExkREaszZNs',
}

/** 云服务客户端（全局单例，各模块共用） */
export const cloud = createWorkBuddyCloud({
  endpoint: PUBLIC_CONFIG.endpoint,
  oauthRelayBaseUrl: PUBLIC_CONFIG.oauthRelayBaseUrl,
  publishableKey: PUBLIC_CONFIG.publishableKey,
})

const SYSTEM_PROMPT =
  '你是「合一重卡生态经营看板」的经营分析助手。请基于输入的经营数据，用简洁、客观的中文给出 2~3 句经营点评：先点出最值得关注的一项，再给出一条可执行的建议。只依据输入数据，不要编造数字。'

/** 由驾驶舱的汇总数据生成一段 AI 经营点评。失败时抛出，由调用方降级。 */
export async function generateInsight(context: string): Promise<string> {
  const models = await cloud.llm.models.list()
  const model = models.find((m) => m.enabled)
  if (!model) throw new Error('暂无可用的大模型')

  let answer = ''
  for await (const chunk of cloud.llm.chat.completions.create({
    model: model.id,
    messages: [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: context },
    ],
    stream: true,
  })) {
    const delta = chunk.choices?.[0]?.delta?.content
    if (delta) answer += delta
  }
  return answer.trim()
}
