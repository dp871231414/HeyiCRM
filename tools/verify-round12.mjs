/**
 * 第十二轮浏览器验收 · 市场项目概览（漏斗）+ 项目管理菜单
 *
 * 用法：BASE_URL=http://127.0.0.1:8000 DIAG_USER=admin DIAG_PWD=123456 node verify-round12.mjs
 * 前置：库里已有市场项目数据（种子或手工灌入的 8 个演示项目）。
 */
import { chromium } from 'playwright-core'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const USER = process.env.DIAG_USER || 'admin'
const PWD = process.env.DIAG_PWD || '123456'

let passed = 0
let failed = 0
const errs = []

function ok(name, cond, extra = '') {
  if (cond) {
    passed++
    console.log(`  ✅ ${name}${extra ? `（${extra}）` : ''}`)
  } else {
    failed++
    console.log(`  ❌ ${name}${extra ? `（${extra}）` : ''}`)
  }
}

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 } })
const page = await ctx.newPage()
page.on('console', (m) => m.type() === 'error' && errs.push(m.text()))
page.on('pageerror', (e) => errs.push(String(e)))

// ---------- 登录 ----------
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
await page.fill('input[type="text"], input:not([type])', USER)
await page.fill('input[type="password"]', PWD)
await page.click('button[type="submit"]')
await page.waitForURL('**/dashboard', { timeout: 10000 })
await page.waitForTimeout(1800)

const api = (path) =>
  page.evaluate(async (p) => {
    const r = await fetch(p, { credentials: 'include' })
    return r.ok ? r.json() : null
  }, `${BASE}${path}`)

// ---------- 1. 市场项目概览模块 ----------
console.log('\n一、市场项目概览模块')
const sectionInfo = await page.evaluate(() => {
  const secs = [...document.querySelectorAll('main section')]
  const idx = (re) => secs.findIndex((s) => re.test(s.innerText))
  return {
    core: idx(/核心指标/),
    funnel: idx(/市场项目概览/),
    compare: idx(/项目公司经营对比/),
  }
})
ok('市场项目概览区块存在', sectionInfo.funnel >= 0, `第 ${sectionInfo.funnel + 1} 个 section`)
ok(
  '位于核心指标之下、项目公司对比之上',
  sectionInfo.core >= 0 && sectionInfo.funnel > sectionInfo.core && (sectionInfo.compare < 0 || sectionInfo.funnel < sectionInfo.compare),
)

const funnel = await api('/api/v1/dashboard/project-funnel')
const funnelSec = await page.evaluate(() => {
  const sec = [...document.querySelectorAll('main section')].find((s) => /市场项目概览/.test(s.innerText))
  return sec ? sec.innerText : ''
})
ok('三个漏斗卡片齐全', /市场项目转化漏斗/.test(funnelSec) && /车辆需求漏斗/.test(funnelSec) && /挂车需求漏斗/.test(funnelSec))
ok('销量预测卡片存在', /销量预测/.test(funnelSec) && /预测牵引车销量/.test(funnelSec) && /预测挂车销量/.test(funnelSec))
ok(
  '六个阶段标签齐全',
  ['项目导入', '市场尽调', '初审通过', '联合评审通过', '签约落地', '交车/投运'].every((t) =>
    funnelSec.includes(t),
  ),
)

// 页面漏斗数字与接口一致（项目数漏斗：右侧加粗数值逐层读取 = 各阶段当前数量）
const countCard = await page.evaluate(() => {
  const sec = [...document.querySelectorAll('main section')].find((s) => /市场项目概览/.test(s.innerText))
  if (!sec) return null
  const card = [...sec.querySelectorAll('.card')].find((c) => /市场项目转化漏斗/.test(c.innerText))
  if (!card) return null
  return {
    counts: [...card.querySelectorAll('b')].map((b) => parseInt(b.innerText)).filter((n) => !Number.isNaN(n)),
    pcts: [...card.querySelectorAll('span.pct')].map((s) => s.innerText.trim()),
    polygons: card.querySelectorAll('svg polygon').length,
    // 阶段标题是否绘制在漏斗层级上（叠加在 SVG 上的 HTML 标签）
    layerLabels: [...card.querySelectorAll('span.funnel-label')].map((t) => t.textContent.trim()),
  }
})
const apiCounts = funnel.stages.map((s) => s.count)
ok('项目数漏斗与接口逐层一致（各阶段当前数量）', JSON.stringify(countCard?.counts) === JSON.stringify(apiCounts), `UI ${countCard?.counts} / API ${apiCounts}`)
ok('漏斗造型为 6 个梯形层（SVG）', countCard?.polygons === 6, `${countCard?.polygons} 个`)
// 标题绘制在漏斗对应层上（项目数漏斗 6 个 <text>，且覆盖六个阶段）
ok(
  '阶段标题绘制在漏斗对应层级上',
  (countCard?.layerLabels?.length ?? 0) === 6 &&
    ['项目导入', '市场尽调', '初审通过', '联合评审通过', '签约落地', '交车/投运'].every((t) => countCard.layerLabels.includes(t)),
  countCard?.layerLabels?.join(' / '),
)
// 右侧百分比 = 各阶段当前数量 / 总量
const totalCount = apiCounts.reduce((a, b) => a + b, 0)
const expPcts = apiCounts.map((v) => (totalCount > 0 ? `${Math.round((v / totalCount) * 1000) / 10}%` : '0%'))
ok('右侧百分比为各阶段当前数量占比', JSON.stringify(countCard?.pcts) === JSON.stringify(expPcts), `UI ${countCard?.pcts} / 期望 ${expPcts}`)
ok(
  '销量预测与接口一致',
  funnelSec.includes(`预测牵引车销量`) &&
    new RegExp(`${funnel.forecast.tractor}\\s*辆`).test(funnelSec.replace(/\n/g, ' ')) &&
    new RegExp(`${funnel.forecast.trailer}\\s*辆`).test(funnelSec.replace(/\n/g, ' ')),
  `牵引 ${funnel.forecast.tractor} / 挂车 ${funnel.forecast.trailer}`,
)

// ---------- 2. 转化概率配置 ----------
console.log('\n二、转化概率配置弹窗')
const cfgBtn = await page.evaluate(() => {
  const sec = [...document.querySelectorAll('main section')].find((s) => /市场项目概览/.test(s.innerText))
  const btn = [...sec.querySelectorAll('button')].find((b) => /配置转化概率/.test(b.innerText))
  btn?.click()
  return !!btn
})
ok('「配置转化概率」按钮存在（admin）', cfgBtn)
await page.waitForTimeout(500)

const modalState = await page.evaluate(() => {
  const modal = [...document.querySelectorAll('input[type="number"]')]
  return { inputs: modal.length, values: modal.map((i) => Number(i.value)) }
})
ok('弹窗含六个概率输入框', modalState.inputs === 6, `${modalState.inputs} 个`)
ok('默认概率与阶段百分比一致', JSON.stringify(modalState.values) === JSON.stringify([10, 25, 50, 75, 90, 100]), modalState.values.join('/'))

// 把 10% 层改为 100% → 预测应上升并与接口一致
await page.evaluate(() => {
  const input = document.querySelector('input[type="number"]')
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(input, '100')
  input.dispatchEvent(new Event('input', { bubbles: true }))
})
await page.waitForTimeout(200)
await page.evaluate(() => {
  ;[...document.querySelectorAll('button')].find((b) => b.innerText.trim() === '保存')?.click()
})
await page.waitForTimeout(1200)
const funnelAfter = await api('/api/v1/dashboard/project-funnel')
const cfgAfter = await api('/api/v1/dashboard/funnel-config')
ok('保存后 10% 层概率已变为 1', cfgAfter.probs.find((p) => p.stage === 10)?.prob === 1)
ok('预测随概率上调而增大', funnelAfter.forecast.tractor > funnel.forecast.tractor, `${funnel.forecast.tractor} → ${funnelAfter.forecast.tractor}`)

// 恢复默认
await page.evaluate(() => {
  const sec = [...document.querySelectorAll('main section')].find((s) => /市场项目概览/.test(s.innerText))
  ;[...sec.querySelectorAll('button')].find((b) => /配置转化概率/.test(b.innerText))?.click()
})
await page.waitForTimeout(400)
await page.evaluate(() => {
  ;[...document.querySelectorAll('button')].find((b) => /恢复默认/.test(b.innerText))?.click()
})
await page.waitForTimeout(200)
await page.evaluate(() => {
  ;[...document.querySelectorAll('button')].find((b) => b.innerText.trim() === '保存')?.click()
})
await page.waitForTimeout(1200)
const cfgRestored = await api('/api/v1/dashboard/funnel-config')
ok('已恢复默认概率', cfgRestored.probs.every((p) => Math.abs(p.prob - p.stage / 100) < 1e-9))

// ---------- 3. 项目管理菜单与列表 ----------
console.log('\n三、项目管理菜单')
await page.goto(`${BASE}/market`, { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)
const marketText = await page.evaluate(() => document.querySelector('main')?.innerText ?? '')
ok('路由 /market 可访问且标题为项目管理', /项目管理/.test(await page.title()) || /共 \d+ 个项目/.test(marketText))
const listApi = await api('/api/v1/market-projects?size=50')
ok('列表行数与接口一致', new RegExp(`共 ${listApi.total} 个项目`).test(marketText.replace(/\s+/g, ' ')), `共 ${listApi.total} 个`)
ok('表头字段齐全', ['项目名称', '项目描述', '牵引车需求', '挂车需求', '项目阶段', '负责人', '创建人', '创建时间', '更新时间'].every((t) => marketText.includes(t)))

/** 轮询等待条件成立（线上环境较慢，固定 sleep 不可靠） */
const waitFor = async (fn, timeout = 10000, interval = 300) => {
  const t0 = Date.now()
  while (Date.now() - t0 < timeout) {
    if (await fn()) return true
    await new Promise((r) => setTimeout(r, interval))
  }
  return false
}

// 幂等：先清掉上次运行可能残留的同名项目（避免 keyword 查出 total=2 干断言）
const stale = await api('/api/v1/market-projects?keyword=验收测试项目-临时&size=50')
for (const it of stale.items ?? []) {
  await page.evaluate(async (id) => {
    await fetch(`/api/v1/market-projects/${id}`, { method: 'DELETE', credentials: 'include' })
  }, it.id)
}
// 漏斗基线：清理残留之后、新建之前现取
const funnelBeforeCreate = await api('/api/v1/dashboard/project-funnel')

// 新建项目
await page.evaluate(() => {
  ;[...document.querySelectorAll('button')].find((b) => b.innerText.trim() === '新建项目')?.click()
})
await page.waitForTimeout(500)
await page.evaluate(() => {
  const setVal = (el, v) => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(el, v)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }
  const inputs = [...document.querySelectorAll('.fixed input, [role="dialog"] input')]
  const nameInput = inputs.find((i) => i.type === 'text' || !i.type)
  setVal(nameInput, '验收测试项目-临时')
  const nums = inputs.filter((i) => i.type === 'number')
  setVal(nums[0], '12')
  setVal(nums[1], '6')
  const textarea = document.querySelector('textarea')
  if (textarea) {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
    setter.call(textarea, '浏览器验收创建，稍后删除')
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
  }
})
await page.waitForTimeout(200)
await page.evaluate(() => {
  ;[...document.querySelectorAll('button')].find((b) => b.innerText.trim() === '保存')?.click()
})
await waitFor(async () => (await api('/api/v1/market-projects?keyword=验收测试项目-临时')).total === 1)
const afterCreate = await api('/api/v1/market-projects?keyword=验收测试项目-临时')
ok('新建项目成功（接口可查）', afterCreate.total === 1 && afterCreate.items[0]?.tractorDemand === 12, afterCreate.items[0]?.id)
const newId = afterCreate.items[0]?.id
ok('创建人自动记录', afterCreate.items[0]?.createdByName?.length > 0, afterCreate.items[0]?.createdByName)

// 新建后漏斗项目数 +1（与上方基线对比）
const funnelAfterCreate = await api('/api/v1/dashboard/project-funnel')
ok('新建后漏斗首层项目数 +1', funnelAfterCreate.stages[0].count === funnelBeforeCreate.stages[0].count + 1, `${funnelBeforeCreate.stages[0].count} → ${funnelAfterCreate.stages[0].count}`)

// 编辑该项目（改阶段为 90）
const editResp = await page.evaluate(async ([base, id]) => {
  const r = await fetch(`${base}/api/v1/market-projects/${id}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: '验收测试项目-临时', description: '已编辑', tractor_demand: 12, trailer_demand: 6, stage: 90, owner: '郑凯' }),
  })
  return r.status
}, [BASE, newId])
ok('编辑项目成功（阶段→90）', editResp === 200)

// 删除该项目（走页面按钮；线上较慢，各步改为轮询等待而非固定 sleep）
await page.goto(`${BASE}/market`, { waitUntil: 'networkidle' })
const rowFound = await waitFor(() =>
  page.evaluate(() => {
    const kw = [...document.querySelectorAll('main input')].find((i) => /搜索/.test(i.placeholder))
    if (!kw) return false
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(kw, '验收测试项目-临时')
    kw.dispatchEvent(new Event('input', { bubbles: true }))
    ;[...document.querySelectorAll('button')].find((b) => b.innerText.trim() === '查询')?.click()
    return [...document.querySelectorAll('main td button')].some((b) => b.innerText.trim() === '删除')
  }),
)
ok('搜索到待删除项目', rowFound)
const confirmShown = await waitFor(() =>
  page.evaluate(() => {
    ;[...document.querySelectorAll('main td button')].find((b) => b.innerText.trim() === '删除')?.click()
    return [...document.querySelectorAll('button')].some((b) => b.innerText.trim() === '确认删除')
  }),
)
ok('删除确认弹窗出现', confirmShown)
await page.evaluate(() => {
  ;[...document.querySelectorAll('button')].find((b) => b.innerText.trim() === '确认删除')?.click()
})
const deleted = await waitFor(async () => (await api('/api/v1/market-projects?keyword=验收测试项目-临时')).total === 0)
ok('删除后接口查不到该项目', deleted)

console.log(`\n控制台错误：${errs.length ? errs.join(' / ') : '0 个 ✅'}`)
console.log(`\n结果：${passed} 通过，${failed} 失败`)
await browser.close()
process.exit(failed ? 1 : 0)
