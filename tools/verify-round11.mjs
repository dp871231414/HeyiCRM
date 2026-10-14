/**
 * 第十一轮专项验收：驾驶舱「部门任务完成度」的展示口径筛选
 *
 * 用法：BASE_URL=http://127.0.0.1:8000 node verify-round11.mjs
 *   可选 DIAG_USER / DIAG_PWD（默认 admin / 123456）、SHOT_DIR（默认 /tmp/ui-shots）
 *
 * 背景：原先这一块只能看全量任务，与页面顶部的统计周期无关也无从筛选。
 * 现在提供 全部 / 本年新增 / 当月新增 / 未结束 四个口径（默认全部），
 * 年与月都取页面顶部周期，卡片的任务数与已完成数随筛选同步。
 *
 * 断言方式：UI 数字与同源接口逐个口径比对（证明连线正确），
 * 再用「当月 ⊆ 本年 ⊆ 全部」「未结束的已完成数为 0」证明筛选真的生效。
 */
import { mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const USER = process.env.DIAG_USER || 'admin'
const PWD = process.env.DIAG_PWD || '123456'
const SHOT_DIR = process.env.SHOT_DIR || '/tmp/ui-shots'
const R = []
const ok = (name, pass, detail = '') => {
  R.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}

mkdirSync(SHOT_DIR, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1600, height: 1000 } }).then((c) => c.newPage())
const errs = []
page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 140)))
page.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 140)))

await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('input[type="password"]', { state: 'visible', timeout: 20000 }).catch(() => {})
await page.locator('input[type="text"], input:not([type])').first().fill(USER)
await page.locator('input[type="password"]').first().fill(PWD)
await page.locator('button:has-text("登录")').first().click()
await page.waitForFunction(() => !!document.querySelector('aside nav'), null, { timeout: 30000 }).catch(() => {})

await page.locator('aside nav a:has-text("驾驶舱")').first().click()
await page.waitForFunction(() => /部门任务完成度/.test(document.body.innerText), null, { timeout: 30000 })
await page.waitForTimeout(1200)

/* ---------- 1. 筛选按钮与默认口径 ---------- */
// 区块位置每次重算：切换周期后页面分区数量可能变化（别用固定下标）
const readSection = () =>
  page.evaluate(() => {
    const sec = [...document.querySelectorAll('main section')].find((s) => /部门任务完成度/.test(s.innerText))
    if (!sec) return null
    const buttons = [...sec.querySelectorAll('button')].filter((b) =>
      ['全部', '本年新增', '当月新增', '未结束'].includes(b.innerText.trim()),
    )
    const cards = {}
    for (const card of sec.querySelectorAll('.card')) {
      const name = card.querySelector('span')?.innerText.trim()
      const m = /(\d+)\s*项任务/.exec(card.innerText)
      const d = /已完成\s*(\d+)/.exec(card.innerText)
      if (name && m) cards[name] = { total: Number(m[1]), done: d ? Number(d[1]) : 0 }
    }
    const lines = sec.innerText.split('\n').map((x) => x.trim()).filter(Boolean)
    return {
      labels: buttons.map((b) => b.innerText.trim()),
      active: buttons.filter((b) => b.className.includes('bg-white')).map((b) => b.innerText.trim()),
      // 标题下面那行小字是口径说明（排除标题本身，否则永远匹配到「部门任务完成度」）
      hint: lines.find((x) => x !== '部门任务完成度' && /任务/.test(x)) ?? '',
      cards,
      empty: /当前筛选条件下暂无任务/.test(sec.innerText),
    }
  })

const first = await readSection()
ok('部门任务完成度区块可定位', !!first, first ? '已找到' : '未找到')
ok(
  '四个筛选按钮齐全（全部 / 本年新增 / 当月新增 / 未结束）',
  ['全部', '本年新增', '当月新增', '未结束'].every((l) => first.labels.includes(l)),
  first.labels.join('、'),
)
ok('默认为「全部」口径', first.active.length === 1 && first.active[0] === '全部', `选中：${first.active.join('、') || '无'}`)
ok('默认口径下渲染出部门卡片', Object.keys(first.cards).length > 0, JSON.stringify(first.cards))

/* ---------- 2. 逐个口径：UI 与接口一致 + 口径之间关系成立 ---------- */
const apiStats = async (filter, period = '') =>
  page.evaluate(
    async ([b, f, p]) => {
      const qs = new URLSearchParams({ filter: f })
      if (p) qs.set('period', p)
      const r = await fetch(`${b}/api/v1/dashboard/dept-task-stats?${qs}`, { credentials: 'include' })
      return r.ok ? r.json() : null
    },
    [BASE, filter, period],
  )

const clickFilter = async (label) => {
  await page.evaluate((l) => {
    const sec = [...document.querySelectorAll('main section')].find((s) => /部门任务完成度/.test(s.innerText))
    const btn = [...sec.querySelectorAll('button')].find((b) => b.innerText.trim() === l)
    btn?.click()
  }, label)
  await page.waitForTimeout(900)
  return readSection()
}

const sum = (cards) => Object.values(cards).reduce((a, c) => ({ total: a.total + c.total, done: a.done + c.done }), { total: 0, done: 0 })
const snapshot = {}
const HINT_OF = {
  all: /全量任务/,
  year: /年内创建/,
  month: /所选月份内创建/,
  open: /未完成/,
}
for (const [label, filter] of [
  ['全部', 'all'],
  ['本年新增', 'year'],
  ['当月新增', 'month'],
  ['未结束', 'open'],
]) {
  const ui = label === '全部' ? first : await clickFilter(label)
  const api = await apiStats(filter)
  const uiSum = sum(ui.cards)
  const apiSum = sum(
    Object.fromEntries((api ?? []).map((s) => [s.deptName, { total: s.total, done: s.done }])),
  )
  snapshot[filter] = { uiSum, apiSum, cards: ui.cards, hint: ui.hint, empty: ui.empty }
  ok(
    `「${label}」卡片数字与接口一致`,
    !!api && uiSum.total === apiSum.total && uiSum.done === apiSum.done,
    `UI 共 ${uiSum.total} 项 / 已完成 ${uiSum.done}｜接口 ${apiSum.total} 项 / 已完成 ${apiSum.done}`,
  )
  ok(
    `「${label}」的口径提示文案正确`,
    HINT_OF[filter].test(ui.hint),
    ui.hint,
  )
}

ok(
  '口径之间关系成立：当月新增 ⊆ 本年新增 ⊆ 全部',
  snapshot.month.uiSum.total <= snapshot.year.uiSum.total &&
    snapshot.year.uiSum.total <= snapshot.all.uiSum.total,
  `全部 ${snapshot.all.uiSum.total} ≥ 本年 ${snapshot.year.uiSum.total} ≥ 当月 ${snapshot.month.uiSum.total}`,
)
ok(
  '筛选真的生效：当月新增的任务数少于全部',
  snapshot.month.uiSum.total < snapshot.all.uiSum.total,
  `当月 ${snapshot.month.uiSum.total} < 全部 ${snapshot.all.uiSum.total}`,
)
ok(
  '「未结束」口径下已完成数为 0',
  snapshot.open.uiSum.done === 0,
  `未结束 ${snapshot.open.uiSum.total} 项 / 已完成 ${snapshot.open.uiSum.done}`,
)
ok(
  '「未结束」口径任务数不超过全部',
  snapshot.open.uiSum.total <= snapshot.all.uiSum.total,
  `未结束 ${snapshot.open.uiSum.total} ≤ 全部 ${snapshot.all.uiSum.total}`,
)
ok('切换口径后卡片仍可渲染（未白屏）', Object.keys(snapshot.open.cards).length > 0, JSON.stringify(snapshot.open.cards))

await page.screenshot({ path: `${SHOT_DIR}/11a-部门任务完成度-未结束.png`, fullPage: true })

/* ---------- 3. 切回「全部」应恢复初始数字 ---------- */
const back = await clickFilter('全部')
ok(
  '切回「全部」数字与初始一致',
  sum(back.cards).total === sum(first.cards).total && sum(back.cards).done === sum(first.cards).done,
  `${sum(back.cards).total} 项 / 已完成 ${sum(back.cards).done}`,
)

/* ---------- 4. 空口径提示（切到没有任务的月份） ---------- */
const emptyMonth = await page.evaluate(
  ([b]) =>
    fetch(`${b}/api/v1/dashboard/dept-task-stats?period=2025-07&filter=month`, { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => d.length),
  [BASE],
)
ok(
  '切到无任务的月份：接口返回空（前端展示空态提示）',
  emptyMonth === 0,
  `2025-07 当月新增 ${emptyMonth} 个部门`,
)

/* ---------- 5. 「当月新增」跟随页面顶部周期（不是服务器当天） ---------- */
// 直接用 DOM 点击：月份选择器是自定义面板，按文本定位比按可访问名稳
// 周期触发器的显示格式是「2026年10月」（不是 2026-10）
const periodText = () =>
  page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')].find((b) => /^\d{4}年\d{1,2}月$/.test(b.innerText.trim()))
    return btn?.innerText.trim() ?? ''
  })

const pickMonth = async (monthText) => {
  await page.evaluate(() => {
    ;[...document.querySelectorAll('button')].find((b) => /^\d{4}年\d{1,2}月$/.test(b.innerText.trim()))?.click()
  }) // 打开周期面板
  await page.waitForTimeout(300)
  await page.evaluate((m) => {
    ;[...document.querySelectorAll('button')].find((b) => b.innerText.trim() === m)?.click()
  }, monthText)
  await page.waitForTimeout(1500)
}

await pickMonth('9月') // 2026-09：造数里没有 9 月创建的任务
const periodLabel = await periodText()
ok('页面顶部周期已切到 2026 年 9 月', periodLabel === '2026年9月', `周期显示 ${periodLabel || '—'}`)

const septMonth = await clickFilter('当月新增')
const septApi = await apiStats('month', '2026-09')
ok(
  '切到无新任务的月份：当月新增为空并展示空态提示',
  septMonth.empty && Object.keys(septMonth.cards).length === 0 && Array.isArray(septApi) && septApi.length === 0,
  `空态=${septMonth.empty}｜卡片 ${Object.keys(septMonth.cards).length} 张｜接口 ${(septApi ?? []).length} 个部门`,
)
await page.screenshot({ path: `${SHOT_DIR}/11b-部门任务完成度-空态.png`, fullPage: true })

const septYear = await clickFilter('本年新增')
const septYearApi = await apiStats('year', '2026-09')
ok(
  '同一周期下「本年新增」仍取年内创建的任务',
  sum(septYear.cards).total === sum(Object.fromEntries((septYearApi ?? []).map((s) => [s.deptName, { total: s.total, done: s.done }]))).total,
  `本年 ${sum(septYear.cards).total} 项｜接口一致`,
)
ok('本年新增不随月份变化（只随年份）', sum(septYear.cards).total === snapshot.year.uiSum.total, `2026-09 与 2026-10 均为 ${snapshot.year.uiSum.total} 项`)

// 还原到当前月
await pickMonth('本月').catch(() => {})

console.log(`\n控制台错误：${errs.length ? errs.join(' / ') : '0 个 ✅'}`)
const pass = R.filter((r) => r.pass).length
console.log(`\n===== 汇总：${pass}/${R.length} 通过 =====`)
await browser.close()
process.exit(pass === R.length ? 0 : 1)
