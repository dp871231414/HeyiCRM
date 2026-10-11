// 云服务连通性自检脚本（在 frontend 目录下运行：node cloud-smoke.mjs）
// 验证：模型目录可读 + 一次流式补全可返回；失败时打印 error.code 与限流信息。
import { createWorkBuddyCloud } from '@tencent-ai/workbuddy-cloud-sdk'

const cloud = createWorkBuddyCloud({
  endpoint: 'https://heyi-fleet-dashboard.app.workbuddy.host',
  oauthRelayBaseUrl: 'https://www.workbuddy.cn/v2/as/genie-baas/oauth',
  publishableKey: 'wbpk_qceQci7k713KUpJUCItWaO_7EMlM42ZXBs9razwDwKOOExkREaszZNs',
})

const models = await cloud.llm.models.list()
const model = models.find((m) => m.enabled)
console.log('MODELS', models.length, '| using', model?.id)

async function once() {
  let answer = ''
  for await (const chunk of cloud.llm.chat.completions.create({
    model: model.id,
    messages: [
      { role: 'system', content: '你是一名经营分析助手。回答要简洁。' },
      { role: 'user', content: '用一句话说明经营看板的综合加权达成率指标的意义。' },
    ],
    stream: true,
  })) {
    const delta = chunk.choices?.[0]?.delta?.content
    if (delta) answer += delta
  }
  return answer.trim()
}

for (let i = 1; i <= 3; i++) {
  try {
    const a = await once()
    console.log(`ATTEMPT_${i}_OK`, a.length, '|', a.slice(0, 120))
    console.log('VERIFY_OK')
    process.exit(0)
  } catch (e) {
    console.log(`ATTEMPT_${i}_ERR`, e?.error?.code ?? e?.constructor?.name, 'retryAfterMs=', e?.retryAfterMs ?? 'n/a', '|', e?.message?.slice(0, 80))
    if (i < 3) await new Promise((r) => setTimeout(r, (e?.retryAfterMs ?? 5000) + 1000))
  }
}
process.exit(1)
