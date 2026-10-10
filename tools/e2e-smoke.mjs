/**
 * 端到端冒烟测试（真实 Chromium）
 *
 * 依赖 playwright（可全局或本地安装）：
 *   npm i -D playwright && npx playwright install chromium
 *
 * 用法：
 *   BASE_URL=http://127.0.0.1:5173 node e2e-smoke.mjs
 *   BASE_URL=https://heyi-fleet-dashboard.app.workbuddy.host node e2e-smoke.mjs
 *
 * 覆盖：登录页渲染 → 管理员登录 → 驾驶舱 → 任务管理 → 指标维护 → 账号管理 → 越权校验
 * 同时收集控制台错误、页面异常与失败请求。
 */
import { mkdirSync } from 'node:fs'

import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173'
const OUT = process.env.SHOT_DIR || '/tmp/fleet_shots'
const ACCOUNT = process.env.E2E_ACCOUNT || 'chenzm'
const PASSWORD = process.env.E2E_PASSWORD || 'Demo#2026'
const MEMBER = process.env.E2E_MEMBER || 'zhengkai'

mkdirSync(OUT, { recursive: true })

const results = []
const record = (name, ok, detail = '') => {
  results.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1600, height: 950 } })
const page = await ctx.newPage()

const consoleErrors = []
const pageErrors = []
const failedRequests = []
page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()))
page.on('pageerror', (e) => pageErrors.push(String(e)))
page.on('requestfailed', (r) => failedRequests.push(`${r.method()} ${r.url()} :: ${r.failure()?.errorText}`))

const step = async (name, fn) => {
  try {
    await fn()
  } catch (e) {
    record(name, false, String(e).split('\n')[0])
  }
}

await step('登录页加载', async () => {
  await page.goto(BASE, { waitUntil: 'networkidle' })
  record('登录页加载', true)
  const body = await page.textContent('body')
  record('品牌名展示', body.includes('合一重卡生态经营看板'))
  record('存在登录输入框', (await page.locator('input').count()) >= 2)
  const h = await page.evaluate(() => document.documentElement.scrollHeight)
  record('登录页无异常撑高', h < 1200, `scrollHeight=${h}`)
  await page.screenshot({ path: `${OUT}/01-login.png`, fullPage: true })
})

await step('管理员登录', async () => {
  const inputs = page.locator('input')
  await inputs.nth(0).fill(ACCOUNT)
  await inputs.nth(1).fill(PASSWORD)
  await page.locator('button:has-text("登录")').first().click()
  await page.waitForTimeout(2500)
  const body = await page.textContent('body')
  record('管理员登录', !body.includes('账号或密码错误'), `url=${page.url()}`)
  await page.screenshot({ path: `${OUT}/02-dashboard.png`, fullPage: true })
  record('驾驶舱渲染指标', body.includes('销售收入') || body.includes('运力收入'))
})

const goto = async (label, file) => {
  await page.locator(`a:has-text("${label}"), button:has-text("${label}")`).first().click()
  await page.waitForTimeout(2000)
  await page.screenshot({ path: `${OUT}/${file}`, fullPage: true })
  return page.textContent('body')
}

await step('任务管理页', async () => {
  const body = await goto('任务管理', '03-tasks.png')
  record('任务管理加载', body.includes('任务名称') || body.includes('任务分类'))
})

await step('指标维护页', async () => {
  const body = await goto('指标维护', '04-metrics.png')
  record('指标维护加载', body.includes('公司整体目标') || body.includes('项目公司'))
})

await step('账号管理页', async () => {
  const body = await goto('账号管理', '05-accounts.png')
  record('账号管理加载', body.includes('账号') || body.includes('组织结构'))
})

await step('越权校验', async () => {
  const resp = await page.request.post(`${BASE}/api/v1/auth/login`, { data: { account: MEMBER, password: PASSWORD } })
  const token = (await resp.json()).access_token
  const r2 = await page.request.get(`${BASE}/api/v1/users`, { headers: { Authorization: `Bearer ${token}` } })
  record('成员越权访问账号列表被拒', r2.status() === 403, `status=${r2.status()}`)
})

await browser.close()

console.log('\n===== 控制台错误 =====')
console.log(consoleErrors.length ? consoleErrors.slice(0, 10).join('\n') : '（无）')
console.log('\n===== 页面异常 =====')
console.log(pageErrors.length ? pageErrors.slice(0, 10).join('\n') : '（无）')
console.log('\n===== 失败请求 =====')
console.log(failedRequests.length ? failedRequests.slice(0, 10).join('\n') : '（无）')

const pass = results.filter((r) => r.ok).length
console.log(`\n===== 汇总：${pass}/${results.length} 通过 =====`)
process.exit(results.some((r) => !r.ok) ? 1 : 0)
