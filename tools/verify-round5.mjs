/**
 * 本轮专项验收
 *
 * A. 角色配置界面：指标维护的编辑权限按「公司整体目标 / 指标监控 / 项目公司指标」三块分组展示
 * B. 指标维护页：趋势数据合并为一次请求，且表格先渲染、不再等趋势回来
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
// 凭据用脚本专用变量（shell 自带的 USER / PWD 已是当前用户名与工作目录）
const LOGIN_USER = process.env.DIAG_USER || 'admin'
const LOGIN_PWD = process.env.DIAG_PWD || '123456'

const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1600, height: 950 } }).then((c) => c.newPage())
const errs = []
page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 140)))

const R = []
const ok = (name, pass, detail = '') => {
  R.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}

const MENU_PATH = { 经营驾驶舱: '/dashboard', 任务管理: '/tasks', 指标维护: '/metrics', 账号管理: '/accounts' }
async function gotoMenu(label, marker = '') {
  await page.click(`aside nav a:has-text("${label}")`)
  const expect = MENU_PATH[label]
  if (expect) {
    await page.waitForFunction((p) => location.pathname.startsWith(p), expect, { timeout: 15000 }).catch(() => {})
  }
  if (marker) {
    await page
      .waitForFunction((m) => (document.querySelector('main')?.innerText || '').includes(m), marker, { timeout: 15000 })
      .catch(() => {})
  }
  await page.waitForTimeout(400)
}

// ---------------- 登录 ----------------
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('input[type="password"]', { state: 'visible', timeout: 20000 }).catch(() => {})
await page.locator('input[type="text"], input:not([type])').first().fill(LOGIN_USER)
await page.locator('input[type="password"]').first().fill(LOGIN_PWD)
await page.locator('button:has-text("登录")').first().click()
await page.waitForFunction(() => !!document.querySelector('aside nav'), null, { timeout: 30000 }).catch(() => {})

// ================= A. 权限按三块分组 =================
console.log('──── A. 角色配置里的编辑权限分组 ────')
await gotoMenu('账号管理', '角色权限')
await page.locator('main button:has-text("角色权限")').first().click().catch(() => {})
await page.waitForTimeout(1200)
await page.locator('main button:has-text("新增角色")').first().click().catch(() => {})
await page.waitForTimeout(1200)

const sections = await page.evaluate(() => {
  const titles = ['公司整体目标', '指标监控', '项目公司指标']
  const found = []
  for (const el of document.querySelectorAll('div')) {
    const t = (el.innerText || '').trim()
    if (titles.includes(t) && el.children.length === 0) {
      const box = el.parentElement
      const items = box
        ? [...box.querySelectorAll('label span')]
            .map((s) => s.innerText.trim())
            .filter((x) => x && x !== t)
        : []
      found.push({ name: t, items })
    }
  }
  // 去掉可能的重复（同一标题被父子元素同时匹配）
  const seen = new Set()
  return found.filter((f) => {
    const k = f.name + '|' + f.items.join(',')
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
})

const names = sections.map((s) => s.name)
ok(
  '编辑权限按三块分组展示',
  ['公司整体目标', '指标监控', '项目公司指标'].every((n) => names.includes(n)),
  names.join(' / ') || '未找到分组标题',
)

const byName = Object.fromEntries(sections.map((s) => [s.name, s.items]))
ok('「公司整体目标」下有对应权限', (byName['公司整体目标'] || []).some((x) => x.includes('公司整体目标')), (byName['公司整体目标'] || []).join('/'))
ok('「指标监控」下有对应权限', (byName['指标监控'] || []).some((x) => x.includes('监控指标')), (byName['指标监控'] || []).join('/'))
ok(
  '「项目公司指标」下含 维护 + 增/改/删',
  ['项目公司指标', '新增项目公司', '编辑项目公司', '删除项目公司'].every((x) =>
    (byName['项目公司指标'] || []).some((y) => y.includes(x)),
  ),
  (byName['项目公司指标'] || []).join('/'),
)
ok('旧的笼统项「录入 / 修改指标」已不再出现', !(byName['指标监控'] || []).some((x) => x.includes('录入')))

await page.locator('.fixed button:has-text("取消")').first().click().catch(() => {})
await page.waitForTimeout(500)

// ================= B. 指标维护页请求合并 =================
console.log('\n──── B. 指标维护页加载 ────')
const reqs = []
page.on('request', (r) => reqs.push(r.url().replace(BASE, '')))

await page.click('aside nav a:has-text("指标维护")')
const t0 = Date.now()
let rendered = false
await page
  .waitForFunction(
    () => {
      const t = document.querySelector('main')?.innerText || ''
      return t.includes('公司整体目标') && !t.includes('加载中')
    },
    null,
    { timeout: 20000 },
  )
  .then(() => (rendered = true))
  .catch(() => {})
const elapsed = Date.now() - t0
ok('指标维护页能在 2 秒内渲染出表格', rendered && elapsed < 2000, `${elapsed}ms`)

await page.waitForTimeout(2500) // 等趋势请求发完（它不阻塞渲染）
const batchTrends = reqs.filter((u) => u.includes('/metrics/trends'))
const singleTrends = reqs.filter((u) => /\/metrics\/[A-Z_]+\/trend/.test(u))
ok(
  '趋势数据只用一次批量请求',
  batchTrends.length === 1 && singleTrends.length === 0,
  `批量 ${batchTrends.length} 次 / 逐个 ${singleTrends.length} 次`,
)
ok('批量请求携带了全部监控指标', /ids=/.test(batchTrends[0] || '') && (batchTrends[0] || '').split('ids=')[1].split(',').length >= 5, (batchTrends[0] || '').slice(0, 70))

const pass = R.filter((r) => r.pass).length
console.log(`\n汇总：${pass}/${R.length} 通过`)
console.log('控制台错误：', errs.length ? errs.join(' / ') : '0 个 ✅')

await browser.close()
process.exit(pass === R.length ? 0 : 1)
