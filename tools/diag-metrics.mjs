/**
 * 诊断：指标维护页的加载耗时与请求构成。
 *
 * 用法：BASE_URL=https://... node diag-metrics.mjs
 *
 * 关注的指标：从点击「指标维护」到表格渲染完成的耗时，以及趋势请求的条数
 * —— 该页面曾为每个监控指标各发一个 trend 请求（10 个并发互相争抢）。
 */
import { chromium } from 'playwright'
const BASE = process.env.BASE_URL
// 凭据用脚本专用变量：shell 自带的 USER / PWD 分别已是当前用户名与工作目录
const LOGIN_USER = process.env.DIAG_USER || 'chenzm'
const LOGIN_PWD = process.env.DIAG_PWD || 'Demo#2026'
const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1600, height: 950 } }).then((c) => c.newPage())

const reqs = []
page.on('requestfinished', async (r) => {
  try {
    const t = await r.timing()
    reqs.push({ url: r.url().replace(BASE, ''), start: Math.round(t.startTime - t0), ttfb: Math.round(t.responseStart - t.requestStart) })
  } catch {}
})
let boardInfo = null
page.on('response', async (r) => {
  if (r.url().includes('/metrics/board')) {
    try {
      const j = await r.json()
      boardInfo = { annual: (j.annual || []).length, monitor: (j.monitor || []).length, projects: (j.project?.companies || []).length, orgId: j.orgId }
    } catch {}
  }
})

const t0 = Date.now()
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('input[type="password"]', { state: 'visible', timeout: 20000 }).catch(() => {})
await page.locator('input[type="text"], input:not([type])').first().fill(LOGIN_USER)
await page.locator('input[type="password"]').first().fill(LOGIN_PWD)
await page.locator('button:has-text("登录")').first().click()
await page.waitForFunction(() => !!document.querySelector('aside nav'), null, { timeout: 30000 }).catch(() => {})
console.log(`登录完成: ${Date.now() - t0}ms`)

// 切到指标维护并计时
reqs.length = 0
const tNav = Date.now()
await page.click('aside nav a:has-text("指标维护")')
let rendered = false
await page.waitForFunction(
  () => {
    const t = document.querySelector('main')?.innerText || ''
    return t.includes('公司整体目标') && !t.includes('加载中')
  },
  null,
  { timeout: 40000 },
).then(() => (rendered = true)).catch(() => {})

console.log(`指标维护页渲染完成: ${Date.now() - tNav}ms  ${rendered ? '' : '（超时未完成）'}`)

// 趋势请求不阻塞渲染，是在表格出现之后才发出 —— 等它跑完再统计
await page.waitForTimeout(3000)
const tSettled = Date.now() - tNav
console.log(`board 内容: ${JSON.stringify(boardInfo)}`)

const byPrefix = {}
for (const r of reqs) {
  const k = r.url.split('?')[0]
  byPrefix[k] = byPrefix[k] || { n: 0, maxTtfb: 0, sum: 0 }
  byPrefix[k].n++
  byPrefix[k].maxTtfb = Math.max(byPrefix[k].maxTtfb, r.ttfb)
  byPrefix[k].sum += r.ttfb
}
console.log(`趋势数据全部到达: ${tSettled}ms（含等待）`)
console.log(`\n切换后请求总数: ${reqs.length}`)
console.log('按接口聚合：')
Object.entries(byPrefix)
  .sort((a, b) => b[1].n - a[1].n)
  .forEach(([k, v]) => console.log(`  ${String(v.n).padStart(3)} 次  平均TTFB ${Math.round(v.sum / v.n)}ms  最大 ${v.maxTtfb}ms  ${k.slice(0, 52)}`))

const sorted = [...reqs].sort((a, b) => a.start - b.start)
console.log(`\n请求时间轴（前 3 与后 3）：`)
sorted.slice(0, 3).forEach((r) => console.log(`  +${String(r.start).padStart(5)}ms  ${r.url.slice(0, 60)}`))
console.log('  ...')
sorted.slice(-3).forEach((r) => console.log(`  +${String(r.start).padStart(5)}ms  ${r.url.slice(0, 60)}`))

await page.screenshot({ path: '/tmp/metrics-page.png' })
await browser.close()
