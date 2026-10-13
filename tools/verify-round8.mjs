/**
 * 第八轮视觉验收：设计系统落地的实际效果与一致性。
 *
 * 检查两件事：
 *   1. 视觉证据 —— 登录页与四个页面各截一张图（供人工确认风格）；
 *   2. 客观判据 —— 品牌色是否已是 Electric Blue、是否仍有旧靛蓝/紫色残留、
 *      是否零外部请求（项目硬约束）、焦点环与阴影是否按新代币生效。
 *
 * 用法：BASE_URL=http://127.0.0.1:8000 node verify-round8.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const ADMIN_USER = process.env.DIAG_USER || 'admin'
const ADMIN_PWD = process.env.DIAG_PWD || '123456'
const SHOT_DIR = process.env.SHOT_DIR || '/tmp/ui-shots'

const R = []
const ok = (name, pass, detail = '') => {
  R.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()

const errs = []
const external = []
const fontReqs = []
page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 140)))
page.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 140)))
page.on('request', (r) => {
  const u = r.url()
  if (!u.startsWith(BASE) && !u.startsWith('data:') && !u.startsWith('blob:')) external.push(u.slice(0, 110))
  if (r.resourceType() === 'font') fontReqs.push(u.slice(0, 110))
})

// ---------- 登录页 ----------
await page.goto(BASE, { waitUntil: 'load' })
await page.waitForSelector('input[type="password"]', { state: 'visible', timeout: 20000 }).catch(() => {})
await page.waitForTimeout(700)
await page.screenshot({ path: `${SHOT_DIR}/1-登录页.png`, fullPage: false })

const loginVisual = await page.evaluate(() => {
  const visual = document.querySelector('.login-visual')
  const label = document.querySelector('.section-label')
  return {
    visualBg: visual ? getComputedStyle(visual).backgroundImage.slice(0, 90) : '',
    hasSectionLabel: !!label,
    labelDotAnimated: label?.querySelector('.section-label-dot')
      ? getComputedStyle(label.querySelector('.section-label-dot')).animationName
      : '',
  }
})
ok('登录页品牌视觉区已应用新渐变', /0, 82, 255|0, 43, 214/.test(loginVisual.visualBg), loginVisual.visualBg.slice(0, 60))
ok('登录页出现区块标识（section-label）', loginVisual.hasSectionLabel)
ok('标识的脉冲点带呼吸动画', loginVisual.labelDotAnimated === 'pulseDot', loginVisual.labelDotAnimated)

// ---------- 登录 ----------
await page.locator('input[type="text"], input:not([type])').first().fill(ADMIN_USER)
await page.locator('input[type="password"]').first().fill(ADMIN_PWD)
await page.locator('button:has-text("登录")').first().click()
await page.waitForFunction(() => !!document.querySelector('aside nav'), null, { timeout: 30000 }).catch(() => {})
await page.waitForTimeout(2600)

/** 校验当前页的品牌色是否为新主色，并顺带统计旧色残留 */
async function checkBrand(pageName, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel)
    const cs = el ? getComputedStyle(el) : null
    const html = document.documentElement.outerHTML
    return {
      css: cs ? `${cs.backgroundColor} | ${cs.color} | ${cs.backgroundImage.slice(0, 60)}` : '(未找到)',
      // 旧靛蓝 #4F46E5 / 紫色 #7C3AED 不应再出现在样式里
      legacy: /4f46e5|7c3aed|99,\s*102,\s*241|124,\s*58,\s*237/i.test(html),
    }
  }, selector)
}

const nav = await checkBrand('侧边栏选中项', 'aside nav a.bg-gradient-to-r')
ok('侧边栏选中项使用新渐变', /0, 82, 255|77, 124, 255/.test(nav.css), nav.css.slice(0, 70))
ok('页面源码中无旧靛蓝/紫色（#4F46E5 / #7C3AED）', !nav.legacy)

// 逐页截图
const pages = [
  ['2-驾驶舱', '驾驶舱'],
  ['3-指标维护', '指标维护'],
  ['4-任务管理', '任务管理'],
  ['5-账号管理', '账号管理'],
]
for (const [file, label] of pages) {
  await page.locator(`aside nav a:has-text("${label}")`).first().click()
  await page.waitForTimeout(2600)
  await page.screenshot({ path: `${SHOT_DIR}/${file}.png`, fullPage: false })
  const info = await page.evaluate(() => {
    // box-shadow 由三个变量拼接（前两段是透明的 ring 占位），必须读完整串再判断，
    // 截断会只看得到前两段透明的部分而误判（本脚本曾因此误报）。
    const btn = document.querySelector('.btn-primary')
    const card = document.querySelector('.card')
    const titles = document.querySelectorAll('.section-title')
    const bcs = btn ? getComputedStyle(btn) : null
    const ccs = card ? getComputedStyle(card) : null
    const tcs = titles.length ? getComputedStyle(titles[0]) : null
    return {
      hasBtn: !!btn,
      btnRadius: bcs?.borderRadius ?? '',
      btnShadow: bcs?.boxShadow ?? '',
      cardRadius: ccs?.borderRadius ?? '',
      cardShadow: ccs?.boxShadow ?? '',
      titleCount: titles.length,
      titleWeight: tcs?.fontWeight ?? '',
      titleTracking: tcs?.letterSpacing ?? '',
    }
  })
  if (info.hasBtn) {
    ok(
      `${label}：主按钮圆角 12px + 品牌色阴影`,
      info.btnRadius.startsWith('12px') && info.btnShadow.includes('0, 82, 255'),
      `${info.btnRadius} / 阴影含品牌色=${info.btnShadow.includes('0, 82, 255')}`,
    )
  }
  ok(
    `${label}：卡片圆角 16px + 品牌色阴影`,
    info.cardRadius.startsWith('16px') && info.cardShadow.includes('0, 82, 255'),
    `${info.cardRadius} / 阴影含品牌色=${info.cardShadow.includes('0, 82, 255')}`,
  )
  if (info.titleCount > 0) {
    // .section-title 是 text-sm（14px），-0.02em × 14px = -0.28px
    ok(
      `${label}：区块标题特粗 + 紧字距`,
      info.titleWeight === '800' && info.titleTracking === '-0.28px',
      `${info.titleCount} 个 · 字重 ${info.titleWeight} · 字距 ${info.titleTracking}`,
    )
  }
}

// ---------- 硬约束：零外部请求 ----------
ok('无外部网络请求（含字体）', external.length === 0, external.slice(0, 2).join(' / ') || '0 个')
ok('未加载任何外部字体文件', fontReqs.length === 0, fontReqs.slice(0, 2).join(' / ') || '0 个')

ok('控制台无错误', errs.length === 0, errs.slice(0, 2).join(' / ') || '0 个')

const pass = R.filter((r) => r.pass).length
console.log(`\n===== 汇总：${pass}/${R.length} 通过 =====`)
const fails = R.filter((r) => !r.pass)
if (fails.length) fails.forEach((f) => console.log(`  - ${f.name} ${f.detail}`))
console.log(`截图目录：${SHOT_DIR}`)

await browser.close()
process.exit(fails.length ? 1 : 0)
