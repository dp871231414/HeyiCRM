/**
 * 本轮需求验收（真实浏览器）
 *
 * A. 统计周期组件交互：面板式选择、年份快速跳转、越界禁用、点击外部 / Esc 关闭
 *    （替换原生 input[type=month] —— 该类型 Safari 不支持，会退化成文本框）
 * B. 项目公司的编辑 / 删除入口：按权限点显隐，不再依赖「当前视角是否为全公司」
 *    （回归点：此前切到项目公司视角后增删改按钮会消失）
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const PWD = 'Demo#2026'
const PANEL = '[role="dialog"][aria-label="选择统计周期"]'
const TRIGGER = 'main button[aria-haspopup="dialog"]'

const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1760, height: 1000 } }).then((c) => c.newPage())
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
    await page
      .waitForFunction((p) => location.pathname.startsWith(p), expect, { timeout: 15000 })
      .catch(() => console.log(`  [导航] 未切到 ${expect}，当前 ${page.url()}`))
  }
  if (marker) {
    await page
      .waitForFunction((m) => (document.querySelector('main')?.innerText || '').includes(m), marker, {
        timeout: 15000,
      })
      .catch(() => console.log(`  [导航] 未等到「${label}」渲染（标记：${marker}）`))
  }
  await page.waitForTimeout(400)
}

const triggerLabel = () =>
  page.evaluate(() => document.querySelector('main button[aria-haspopup="dialog"]')?.innerText.trim() || '')

/** 读取面板内月份按钮的可用状态 */
const monthStates = () =>
  page.evaluate(() => {
    const panel = document.querySelector('[role="dialog"][aria-label="选择统计周期"]')
    if (!panel) return {}
    const out = {}
    for (const b of panel.querySelectorAll('button')) {
      const t = b.innerText.trim()
      if (/^\d{1,2}月$/.test(t)) out[String(Number(t.replace('月', '')))] = b.disabled
    }
    return out
  })

/** 读取面板内年份按钮文字 */
const yearList = () =>
  page.evaluate(() =>
    [...document.querySelectorAll('[role="dialog"][aria-label="选择统计周期"] button')]
      .map((b) => b.innerText.trim())
      .filter((t) => /^\d{4}$/.test(t)),
  )

const panelCount = () => page.locator(PANEL).count()

// ---------------- 登录 ----------------
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.fill('input[type="text"], input:not([type])', 'chenzm').catch(() => {})
const pw = page.locator('input[type="password"]')
if (await pw.count()) {
  await pw.fill(PWD)
  await page.click('button[type="submit"], button:has-text("登录")')
}
await page.waitForTimeout(4500)

// ================= A. 统计周期组件 =================
console.log('──── A. 统计周期组件交互 ────')
await gotoMenu('经营驾驶舱', '核心指标')

const initial = await triggerLabel()
ok('触发器显示「YYYY年M月」而非原始值', /^\d{4}年\d{1,2}月$/.test(initial), initial)
ok('触发器带图标', (await page.locator(`${TRIGGER} svg`).count()) >= 2)

await page.locator(TRIGGER).first().click()
await page.waitForTimeout(400)
ok('点击后展开选择面板', (await panelCount()) === 1)

const months = await page.evaluate(() =>
  [...document.querySelectorAll('[role="dialog"][aria-label="选择统计周期"] button')]
    .map((b) => b.innerText.trim())
    .filter((t) => /^\d{1,2}月$/.test(t)),
)
ok('面板以 3×4 网格展示 12 个月', months.length === 12, months.join(' '))

const sel = await page.evaluate(() => {
  const panel = document.querySelector('[role="dialog"][aria-label="选择统计周期"]')
  const btn = [...panel.querySelectorAll('button')].find((b) => b.getAttribute('aria-pressed') === 'true')
  return btn ? { text: btn.innerText.trim(), filled: /bg-brand-600/.test(btn.className) } : null
})
ok('选中月份以主色填充', !!sel && sel.filled, sel ? sel.text : '未找到')

const disA = await monthStates()
ok('低于下界（2026-09）的月份被禁用', disA['1'] === true && disA['8'] === true, `1月=${disA['1']} 8月=${disA['8']}`)
ok('范围内的月份可选', disA['9'] === false && disA['12'] === false, `9月=${disA['9']} 12月=${disA['12']}`)

ok('面板标注可选范围', /2026-09/.test(await page.locator(PANEL).innerText()) && /2099-12/.test(await page.locator(PANEL).innerText()))

// 年份快速跳转
await page.evaluate(() => {
  const panel = document.querySelector('[role="dialog"][aria-label="选择统计周期"]')
  const t = [...panel.querySelectorAll('button')].find((b) => /^\d{4}年$/.test(b.innerText.trim()))
  t?.click()
})
await page.waitForTimeout(300)
const years = await yearList()
ok('点年份标题切换到年份面板', years.length === 12, years.join(' '))

let reached2099 = false
for (let i = 0; i < 12; i++) {
  if ((await yearList()).includes('2099')) {
    reached2099 = true
    break
  }
  const moved = await page.evaluate(() => {
    const n = [...document.querySelectorAll('[role="dialog"][aria-label="选择统计周期"] button')].find(
      (b) => b.getAttribute('aria-label') === '下一页',
    )
    if (!n || n.disabled) return false
    n.click()
    return true
  })
  if (!moved) break
  await page.waitForTimeout(220)
}
ok('年份面板可翻页直接够到 2099（无需逐年点击）', reached2099)

// 上限年是 2099，因此该年 12 个月均有效；越界体现在年份面板（2100 起禁用）
const yearDisabled = await page.evaluate(() => {
  const b = [...document.querySelectorAll('[role="dialog"][aria-label="选择统计周期"] button')].find(
    (x) => x.innerText.trim() === '2100',
  )
  return b ? b.disabled : null
})
ok('年份面板中超出 2099 的年份被禁用', yearDisabled === true, `2100 禁用=${yearDisabled}`)

await page.evaluate(() => {
  const b = [...document.querySelectorAll('[role="dialog"][aria-label="选择统计周期"] button')].find(
    (x) => x.innerText.trim() === '2099',
  )
  b?.click()
})
await page.waitForTimeout(300)
const dis99 = await monthStates()
ok('2099 年整年可选（上限月为 2099-12）', dis99['1'] === false && dis99['12'] === false, `1月=${dis99['1']} 12月=${dis99['12']}`)

await page.evaluate(() => {
  const b = [...document.querySelectorAll('[role="dialog"][aria-label="选择统计周期"] button')].find(
    (x) => x.innerText.trim() === '12月',
  )
  b?.click()
})
await page.waitForTimeout(1600)
ok('选择后自动关闭面板', (await panelCount()) === 0)
ok('触发器同步为所选项', (await triggerLabel()) === '2099年12月', await triggerLabel())

// 点击外部关闭
await page.locator(TRIGGER).first().click()
await page.waitForTimeout(350)
await page.mouse.click(1300, 40)
await page.waitForTimeout(350)
ok('点击面板外部自动关闭', (await panelCount()) === 0)

// Esc 关闭
await page.locator(TRIGGER).first().click()
await page.waitForTimeout(350)
await page.keyboard.press('Escape')
await page.waitForTimeout(350)
ok('Esc 键关闭面板', (await panelCount()) === 0)

// 还原为当前周期，避免影响后续断言
await page.evaluate(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  document.querySelector('main button[aria-haspopup="dialog"]')?.click()
  await sleep(400)
  const panel = document.querySelector('[role="dialog"][aria-label="选择统计周期"]')
  const title = [...panel.querySelectorAll('button')].find((b) => /^\d{4}年$/.test(b.innerText.trim()))
  title?.click()
  await sleep(300)
  // 翻回第一页（含 2026）
  for (let i = 0; i < 12; i++) {
    const years = [...panel.querySelectorAll('button')].map((b) => b.innerText.trim())
    if (years.includes('2026')) break
    const prev = [...panel.querySelectorAll('button')].find((b) => b.getAttribute('aria-label') === '上一页')
    if (!prev || prev.disabled) break
    prev.click()
    await sleep(200)
  }
  ;[...panel.querySelectorAll('button')].find((b) => b.innerText.trim() === '2026')?.click()
  await sleep(300)
  ;[...panel.querySelectorAll('button')].find((b) => b.innerText.trim() === '10月')?.click()
  await sleep(1200)
})
ok('可还原为当前周期 2026年10月', (await triggerLabel()) === '2026年10月', await triggerLabel())

// ================= B. 项目公司增删改入口 =================
console.log('\n──── B. 项目公司的编辑 / 删除入口 ────')
await gotoMenu('指标维护', '公司整体目标')

/** 读项目公司行上的操作按钮 */
const rowButtons = () =>
  page.evaluate(() => {
    const row = [...document.querySelectorAll('main tbody tr')].find((r) => /负责人/.test(r.innerText))
    return row ? [...row.querySelectorAll('button')].map((b) => b.innerText.trim()) : []
  })

const inCo = await rowButtons()
ok('全公司视角：项目公司行含「删除」', inCo.includes('删除'), inCo.join('/'))
ok('全公司视角：项目公司行含「编辑」', inCo.includes('编辑'))
ok('存在「新增项目公司」入口', (await page.locator('main button:has-text("新增项目公司")').count()) > 0)

// 切到项目公司视角 —— 本轮核心回归点
const orgSel = page.locator('header select').first()
const pcOpt = await page.evaluate(
  () => [...document.querySelectorAll('header select option')].map((o) => o.value).find((v) => v.startsWith('PC')) || '',
)
if (pcOpt) {
  await orgSel.selectOption(pcOpt)
  await page.waitForTimeout(2600)
}
const inPc = await rowButtons()
ok(
  '切到项目公司视角后「删除」入口仍在（本轮修复点）',
  inPc.includes('删除'),
  `视野=${pcOpt} 按钮=${inPc.join('/') || '无'}`,
)
ok('切到项目公司视角后「编辑」入口仍在', inPc.includes('编辑'), inPc.join('/') || '无')

// 删除确认弹窗（只看不删）
await page.locator('main button:has-text("删除")').first().click()
await page.waitForTimeout(1000)
const dlg = await page.evaluate(() => {
  const t = document.body.innerText
  return { opened: /确认删除项目公司/.test(t), impact: /年度目标/.test(t) && /累计完成值/.test(t) }
})
ok('删除前弹出确认对话框', dlg.opened)
ok('确认框展示连带影响（目标 / 完成值 / 任务 / 账号）', dlg.impact)
await page.locator('.fixed button:has-text("取消")').first().click().catch(() => {})
await page.waitForTimeout(600)

// 切回全公司
await orgSel.selectOption('CO').catch(() => {})
await page.waitForTimeout(1600)

// ---------------- 汇总 ----------------
const pass = R.filter((r) => r.pass).length
console.log(`\n汇总：${pass}/${R.length} 通过`)
console.log('控制台错误：', errs.length ? errs.join(' / ') : '0 个 ✅')

await browser.close()
process.exit(pass === R.length ? 0 : 1)
