/**
 * 首次加载性能诊断：采集完整的加载时间线（冷缓存，模拟首次访问）。
 *
 * 用法：
 *   BASE_URL=https://heyi-fleet-dashboard.app.workbuddy.host node diag-load.mjs
 *
 * 输出三个关键时间点（导航发起为 0）：
 *   - DOMContentLoaded：页面骨架就绪
 *   - 登录完成：进入主界面
 *   - 驾驶舱内容出现：用户真正看到数据
 * 以及每个请求的发起时刻与 TTFB，用于识别「串行等待」的环节。
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const browser = await chromium.launch()
// 全新 context = 无缓存，等价于首次访问
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await ctx.newPage()

const t0 = Date.now()
const reqs = []
page.on('requestfinished', async (r) => {
  try {
    const t = await r.timing()
    reqs.push({
      url: r.url().replace(BASE, ''),
      type: r.resourceType(),
      start: Math.round(t.startTime - t0),
      ttfb: Math.round(t.responseStart - t.requestStart),
      total: Math.round(t.responseEnd - t.requestStart),
    })
  } catch {
    /* 忽略无法取到 timing 的请求 */
  }
})

await page.goto(BASE, { waitUntil: 'domcontentloaded' })
const tDomReady = Date.now() - t0

await page.fill('input[type="text"], input:not([type])', process.env.USER || 'chenzm')
const pw = page.locator('input[type="password"]')
if (await pw.count()) {
  await pw.fill(process.env.PWD || 'Demo#2026')
  await page.click('button[type="submit"], button:has-text("登录")')
}
await page.waitForFunction(() => !!document.querySelector('aside nav'), null, { timeout: 30000 }).catch(() => {})
const tLoggedIn = Date.now() - t0
await page
  .waitForFunction(() => (document.querySelector('main')?.innerText || '').length > 40, null, { timeout: 30000 })
  .catch(() => {})
const tContent = Date.now() - t0

const nav = await page.evaluate(() => {
  const n = performance.getEntriesByType('navigation')[0]
  const fcp = performance.getEntriesByName('first-contentful-paint')[0]
  return {
    ttfb: Math.round(n.responseStart),
    dcl: Math.round(n.domContentLoadedEventEnd),
    load: Math.round(n.loadEventEnd),
    fcp: fcp ? Math.round(fcp.startTime) : null,
  }
})

console.log(`目标：${BASE}\n`)
console.log('═══ 关键时间点（毫秒，导航发起为 0）═══')
console.log(`  DOMContentLoaded        : ${tDomReady}`)
console.log(`  登录完成（进入主界面）   : ${tLoggedIn}`)
console.log(`  主内容出现              : ${tContent}`)
console.log(`  navigation 指标：TTFB=${nav.ttfb}  FCP=${nav.fcp}  DCL=${nav.dcl}  load=${nav.load}`)

console.log('\n═══ 请求明细（按发起时刻排序）═══')
const sorted = [...reqs].sort((a, b) => a.start - b.start)
console.log(`  ${'起(ms)'.padStart(7)} ${'TTFB'.padStart(6)} ${'类型'.padEnd(11)} 资源`)
for (const r of sorted) {
  console.log(`  ${String(r.start).padStart(7)} ${String(r.ttfb).padStart(6)} ${(r.type || '').padEnd(11)} ${r.url.slice(0, 58)}`)
}

const api = sorted.filter((r) => r.url.startsWith('/api'))
const assets = sorted.filter((r) => r.url.startsWith('/assets'))
const avg = (list) => (list.length ? Math.round(list.reduce((a, r) => a + r.ttfb, 0) / list.length) : 0)

console.log('\n═══ 汇总 ═══')
console.log(`  请求总数 ${sorted.length}（API ${api.length} / 静态资源 ${assets.length}）`)
console.log(`  平均 TTFB：API ${avg(api)}ms，静态资源 ${avg(assets)}ms`)
console.log(`  最慢的 3 个请求：`)
;[...sorted]
  .sort((a, b) => b.ttfb - a.ttfb)
  .slice(0, 3)
  .forEach((r) => console.log(`    TTFB ${r.ttfb}ms  ${r.url.slice(0, 56)}`))

await browser.close()
