/**
 * 第十轮专项验收：驾驶舱与指标维护的状态口径一致
 *
 * 用法：BASE_URL=http://127.0.0.1:8000 node verify-round10.mjs
 *   可选 DIAG_USER / DIAG_PWD（默认 admin / 123456）、SHOT_DIR（默认 /tmp/ui-shots）
 *
 * 背景：此前两页判据不同 —— 驾驶舱按「达成率 ÷ 时间进度」，指标维护按「实际 vs 目标」
 * （年度目标未走完就一律红），同一指标会同时出现「领先」与「未达标」两种说法。
 * 现在判定统一在服务端 progress_tone，本脚本核对两页渲染出的状态**逐指标一致**，
 * 以及汇总统计的标签与卡片同源。
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

const goto = async (label, marker) => {
  await page.locator(`aside nav a:has-text("${label}")`).first().click()
  await page.waitForFunction((m) => new RegExp(m).test(document.body.innerText), marker, { timeout: 30000 }).catch(() => {})
  await page.waitForTimeout(2200)
}

/* ---------- 1. 驾驶舱：卡片徽章 + 汇总统计标签 ---------- */
await goto('驾驶舱', '核心指标')
const dash = await page.evaluate(() => {
  // 只看「核心指标」这一节 —— 页面别处（部门完成度、分析总结）也有 .chip，会误采
  const sec = [...document.querySelectorAll('main section')].find((s) => /核心指标/.test(s.innerText))
  const cards = {}
  if (sec) {
    // 收入类卡片是 <button class="card">，非收入类是 <div class="card">，统一按 .card 取
    for (const card of sec.querySelectorAll('.card')) {
      const chip = card.querySelector('.chip')
      const name = chip?.previousElementSibling?.innerText.trim()
      if (name && chip) cards[name] = chip.innerText.trim()
    }
  }
  // 分析总结卡：用「位置」定位（main 里的第一个 section），不按文案匹配 ——
  // 按文案匹配的话，后端一改措辞断言就假失败（这个坑踩过两次）。
  const summarySec = (() => {
    const first = document.querySelector('main section')
    return first && /综合加权达成率/.test(first.innerText) ? first : null
  })()
  const counts = {}
  if (summarySec) {
    // 右上角那组统计小卡：上面是数字、下面是标签
    for (const box of summarySec.querySelectorAll('div.rounded-xl')) {
      const lines = box.innerText.split('\n').map((x) => x.trim()).filter(Boolean)
      if (lines.length >= 2) counts[lines[1]] = Number(lines[0])
    }
  }
  return {
    cards,
    counts,
    chip: summarySec?.querySelector('.chip')?.innerText.trim() ?? '',
    summaryText: summarySec?.innerText.replace(/\s+/g, ' ') ?? '',
    body: document.body.innerText,
  }
})
ok('驾驶舱渲染出核心指标卡', Object.keys(dash.cards).length > 0, `共 ${Object.keys(dash.cards).length} 张`)
ok(
  '汇总统计标签与卡片同源（已达成/领先/偏慢/滞后/未录入）',
  ['已达成', '领先', '偏慢', '滞后', '未录入'].every((k) => k in dash.counts),
  JSON.stringify(dash.counts),
)
ok('驾驶舱不再出现「未达标 / 接近目标」的旧说法', !/未达标|接近目标/.test(dash.body))

/* ---------- 1b. 整体结论也走同一套判定（达成率 ÷ 时间进度） ---------- */
const weighted = Number(/综合加权达成率\s*([\d.]+)%/.exec(dash.summaryText)?.[1])
const timeProg = Number(/年度时间进度\s*([\d.]+)%/.exec(dash.summaryText)?.[1])
const ratio = weighted && timeProg ? weighted / timeProg : NaN
const expectChip = !Number.isFinite(ratio)
  ? ''
  : ratio >= 1
    ? '跑赢时间进度'
    : ratio >= 0.7
      ? '略慢于时间进度'
      : '滞后时间进度'
ok(
  '整体结论按「达成率 ÷ 时间进度」判档（阈值 1 / 0.7）',
  !!dash.chip && dash.chip === expectChip,
  `加权 ${weighted}% ÷ 时间进度 ${timeProg}% = ${Number.isFinite(ratio) ? ratio.toFixed(2) : '—'}｜徽章「${dash.chip}」应为「${expectChip}」`,
)
ok(
  '整体结论文案与事实一致（跑赢时间进度时不写「低于时间轴」）',
  !/低于时间轴/.test(dash.summaryText) || ratio < 1,
  dash.summaryText.slice(0, 110),
)

await page.screenshot({ path: `${SHOT_DIR}/10a-驾驶舱-状态.png` })

/* ---------- 2. 指标维护：同一批指标的状态列 ---------- */
await goto('指标维护', '公司整体目标')
const metrics = await page.evaluate(() => {
  const rows = {}
  for (const tr of document.querySelectorAll('main table tbody tr')) {
    const first = tr.querySelector('td')
    const chip = tr.querySelector('.chip')
    if (!first || !chip) continue
    const name = first.innerText.trim().split('\n')[0].trim()
    if (!name) continue
    rows[name] = chip.innerText.trim()
  }
  return { rows, body: document.body.innerText }
})
ok('指标维护渲染出指标行', Object.keys(metrics.rows).length > 0, `共 ${Object.keys(metrics.rows).length} 行`)
ok('指标维护不再出现「未达标 / 接近目标」的旧说法', !/未达标|接近目标/.test(metrics.body))

await page.screenshot({ path: `${SHOT_DIR}/10b-指标维护-状态.png`, fullPage: true })

/* ---------- 3. 逐指标比对两页状态 ---------- */
const common = Object.keys(dash.cards).filter((k) => k in metrics.rows)
ok('两页有可比的同名指标', common.length > 0, `可比 ${common.length} 项：${common.join('、')}`)

const diff = common.filter((k) => dash.cards[k] !== metrics.rows[k])
ok(
  '同一指标在两页的状态完全一致',
  diff.length === 0,
  diff.length
    ? diff.map((k) => `${k}（驾驶舱「${dash.cards[k]}」/ 指标维护「${metrics.rows[k]}」）`).join('；')
    : common.map((k) => `${k}→${dash.cards[k]}`).join(' '),
)

/* ---------- 4. 汇总统计数字与卡片分布一致 ---------- */
const dist = {}
for (const k of common) dist[dash.cards[k]] = (dist[dash.cards[k]] ?? 0) + 1
const mismatch = Object.entries(dist).filter(([label, n]) => (dash.counts[label] ?? -1) !== n)
ok(
  '汇总统计数字与卡片标签分布一致（就可见指标而言）',
  mismatch.length === 0,
  Object.entries(dash.counts).map(([k, v]) => `${k}=${v}`).join(' ') + `｜卡片分布 ${JSON.stringify(dist)}`,
)

console.log(`\n控制台错误：${errs.length ? errs.join(' / ') : '0 个 ✅'}`)
const pass = R.filter((r) => r.pass).length
console.log(`\n===== 汇总：${pass}/${R.length} 通过 =====`)
await browser.close()
process.exit(pass === R.length ? 0 : 1)
