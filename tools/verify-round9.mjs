/**
 * 第九轮专项验收：驾驶舱「分析总结卡改浅色」 + 「核心指标配色统一」
 *
 * 用法：BASE_URL=http://127.0.0.1:8000 node verify-round9.mjs
 *   可选 DIAG_USER / DIAG_PWD 指定账号（默认 admin / 123456）
 *   SHOT_DIR 指定截图目录（默认 /tmp/ui-shots）
 *
 * 核对两件事：
 *   1. 分析总结卡是浅色底（不再是深色反转卡），且状态仍可辨（语义色条 + 徽章）；
 *   2. 核心指标卡里，状态徽章 / 达成率文字 / 进度条三者取同一套颜色，
 *      且该颜色符合「完成率 ÷ 时间进度」的比值规则。
 *
 * 脚本只读、不改数据：比值规则用的是「页面渲染出的色相」与「接口返回的完成率」对照，
 * 因此对任何数据都成立。若要覆盖全部四档颜色（绿/蓝/黄/红），需要先造数据，例如
 * 把时间进度 78.4% 下的目标值调成让比值分别落在 ≥1、0.7~1、<0.7，并让一项达成率 ≥ 100%：
 *
 *   python -c "
 *   import sqlite3
 *   con = sqlite3.connect('dev.db')
 *   con.execute(\"UPDATE metric_target SET value=7000  WHERE metric_id='REV_ENER' AND org_id='CO' AND period='2026'\")
 *   con.execute(\"UPDATE metric_target SET value=15700 WHERE metric_id='REV_SALE' AND org_id='CO' AND period='2026'\")
 *   con.execute(\"UPDATE metric_target SET value=42640 WHERE metric_id='REV_TRANS' AND org_id='CO' AND period='2026'\")
 *   con.commit()"
 *
 * 验完记得把目标值改回去（改前先备份 metric_target 表）。
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
await page
  .waitForFunction(() => /核心指标/.test(document.body.innerText) && !/数据加载中/.test(document.body.innerText), null, {
    timeout: 30000,
  })
  .catch(() => {})
await page.waitForTimeout(2000)

/* ---------- 1. 分析总结卡：底色应当为浅色 ---------- */
const summary = await page.evaluate(() => {
  // 分析总结是页面上第一个带状态徽章的卡片
  const section = [...document.querySelectorAll('main section')].find((s) =>
    /整体良好|需要关注|存在风险|暂无数据/.test(s.innerText),
  )
  if (!section) return null
  const cs = getComputedStyle(section)
  const rgb = cs.backgroundColor.match(/\d+/g)?.map(Number) ?? []
  const lum = rgb.length >= 3 ? (rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114) / 255 : -1
  const accent = section.querySelector('div[class*="absolute"][class*="w-1"]')
  const chip = section.querySelector('.chip')
  return {
    bg: cs.backgroundColor,
    lum,
    hasAccentBar: !!accent,
    accentBg: accent ? getComputedStyle(accent).backgroundColor : '',
    chipText: chip?.innerText.trim() ?? '',
    chipBg: chip ? getComputedStyle(chip).backgroundColor : '',
    headlineColor: getComputedStyle(section.querySelector('p')).color,
  }
})
ok('分析总结卡存在', !!summary, summary ? `底色 ${summary.bg}` : '未找到')
ok('分析总结卡为浅色底（不再是深色反转卡）', summary?.lum > 0.9, summary ? `亮度 ${summary.lum.toFixed(2)}` : '')
ok('保留语义色条用于区分状态', summary?.hasAccentBar && /rgb/.test(summary.accentBg), summary?.accentBg)
ok('状态徽章为浅色底 + 深色字', /rgb\(2[0-9]{2}/.test(summary?.chipBg || ''), `${summary?.chipText} · ${summary?.chipBg}`)

await page.screenshot({ path: `${SHOT_DIR}/9a-驾驶舱-总结卡.png` })

/* ---------- 2. 核心指标卡：三者同色 + 符合比值规则 ---------- */
const cards = await page.evaluate(() => {
  /** 从 className 里取语义色相名（good / brand / warn / bad / slate）——
   *  比匹配 rgb 更稳：不同层级用的色阶深浅不同（500 / 600 / 50…），rgb 会变、色相名不变。 */
  const hue = (el) => {
    if (!el) return null
    const m = /(?:^|\s)(?:bg|text|border)-(good|brand|warn|bad|slate)-/.exec(el.className)
    return m ? m[1] : null
  }
  const HUE_TONE = { good: 'done', brand: 'ahead', warn: 'near', bad: 'risk', slate: 'none' }
  const out = []
  for (const btn of document.querySelectorAll('main section button')) {
    const name = btn.querySelector('span')?.innerText.trim()
    if (!name) continue
    const bar = [...btn.querySelectorAll('div')].find((d) => /(?:^|\s)h-full(?:\s|$)/.test(d.className))
    const chip = btn.querySelector('.chip')
    const rateEl = [...btn.querySelectorAll('span')].find(
      (s) => s.classList.contains('font-bold') && /%|—|∞/.test(s.innerText),
    )
    const chipHue = hue(chip)
    const barHue = hue(bar)
    const rateHue = hue(rateEl)
    out.push({
      name,
      chipText: chip?.innerText.trim() ?? '',
      chipHue,
      barHue,
      rateHue,
      barTone: barHue ? HUE_TONE[barHue] : null,
      badgeTone: chipHue ? HUE_TONE[chipHue] : null,
      rateText: rateEl?.innerText.trim() ?? '',
    })
  }
  return out
})

ok('核心指标卡渲染出进度条', cards.length > 0 && cards.every((c) => !!c.barHue), `共 ${cards.length} 张`)

const mixed = cards.filter((c) => !(c.chipHue === c.barHue && c.barHue === c.rateHue))
ok(
  '同一张卡内：状态徽章 / 达成率文字 / 进度条 三者同色',
  mixed.length === 0,
  mixed.length
    ? mixed.map((c) => `${c.name}(徽章${c.chipHue}/文字${c.rateHue}/条${c.barHue})`).join(' ')
    : `全部一致（${cards.map((c) => c.name + '→' + c.barHue).join(' ')}）`,
)

/* 用接口返回的真实数据核对比值规则 */
const ratios = await (async () => {
  const res = await page.context().request.get(`${BASE}/api/v1/dashboard/overview?org_id=CO`)
  if (!res.ok()) return null
  const j = await res.json()
  return { tp: j.timeProgress, rows: (j.annual ?? []).map((r) => ({ id: r.metricId, name: r.name, rate: r.rate })) }
})()

if (ratios) {
  const expect = (rate) => {
    if (rate === null) return 'none'
    if (rate >= 1) return 'done'
    if (!(ratios.tp > 0)) return 'none'
    const q = rate / ratios.tp
    if (q >= 1) return 'ahead'
    if (q >= 0.7) return 'near'
    return 'risk'
  }
  const expectMap = new Map(ratios.rows.map((r) => [r.name, expect(r.rate)]))
  const wrong = cards.filter((c) => expectMap.has(c.name) && expectMap.get(c.name) !== c.barTone)
  const detail = cards
    .map((c) => {
      const row = ratios.rows.find((r) => r.name === c.name)
      const q = row && row.rate !== null && ratios.tp > 0 ? (row.rate / ratios.tp).toFixed(2) : '—'
      return `${c.name}: 完成率${row?.rate === null || row?.rate === undefined ? '—' : (row.rate * 100).toFixed(1) + '%'} ÷ 时间进度${(ratios.tp * 100).toFixed(1)}% = ${q} → ${c.barTone}`
    })
    .join('\n       ')
  ok('进度条颜色符合「完成率 ÷ 时间进度」规则', wrong.length === 0, `\n       ${detail}`)
  console.log(`\n  时间进度：${(ratios.tp * 100).toFixed(1)}%`)
  console.log(`  卡片明细：\n       ${detail}`)
}

await page.screenshot({ path: `${SHOT_DIR}/9b-驾驶舱-核心指标.png`, fullPage: true })

console.log(`\n控制台错误：${errs.length ? errs.join(' / ') : '0 个 ✅'}`)
const pass = R.filter((r) => r.pass).length
console.log(`\n===== 汇总：${pass}/${R.length} 通过 =====`)
await browser.close()
process.exit(pass === R.length ? 0 : 1)
