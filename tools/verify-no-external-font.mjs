/** 验证移除 Google Fonts 后的效果：无外部请求、控制台零错误、字体回退生效 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1680, height: 1000 } }).then((c) => c.newPage())

const errs = []
const external = []
const fonts = []
page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 160)))
page.on('requestfailed', (r) => errs.push(`FAILED ${r.url().slice(0, 90)} ${r.failure()?.errorText ?? ''}`))
page.on('request', (r) => {
  const u = r.url()
  if (!u.startsWith(BASE) && !u.startsWith('data:') && !u.startsWith('blob:')) external.push(u.slice(0, 110))
  if (r.resourceType() === 'font') fonts.push(u.slice(0, 110))
})

const t0 = Date.now()
await page.goto(BASE, { waitUntil: 'load' })
const loadMs = Date.now() - t0

await page.fill('input[type="text"], input:not([type])', 'admin').catch(() => {})
const pw = page.locator('input[type="password"]')
if (await pw.count()) {
  await pw.fill(process.env.DIAG_PWD || '123456')
  await page.click('button[type="submit"], button:has-text("登录")')
}
await page.waitForTimeout(4000)

const fontInfo = await page.evaluate(() => {
  const el = document.querySelector('main, body')
  const cs = getComputedStyle(el)
  const t = document.querySelector('main h2, main .text-sm, body')
  return {
    family: cs.fontFamily,
    sampleFamily: t ? getComputedStyle(t).fontFamily : '',
    rendered: getComputedStyle(document.body).fontSize,
  }
})

console.log('页面 URL      :', page.url())
console.log('load 事件耗时 :', loadMs, 'ms')
console.log('计算字体栈    :', fontInfo.family)
console.log('外部请求      :', external.length ? external.join(' | ') : '无 ✅')
console.log('字体文件请求  :', fonts.length ? fonts.join(' | ') : '无（全走系统字体）✅')
console.log('控制台错误    :', errs.length ? errs.join(' | ') : '0 个 ✅')

const pass = external.length === 0 && errs.length === 0
console.log(`\n===== ${pass ? '通过：无外链、零错误' : '未通过'} =====`)
await browser.close()
process.exit(pass ? 0 : 1)
