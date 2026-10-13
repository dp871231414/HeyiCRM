/**
 * 本轮四项需求验收（真实浏览器）。
 * 1 统计周期：顶栏无 / 驾驶舱有 / 指标维护有 / 任务管理无，且为月份组件、范围受限
 * 2 累计完成值文案
 * 3 任务管理：创建时间 + 更新时间列；按部门分组视图带小标题
 * 4 权限说明文案（不写死角色）
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const PWD = process.env.DIAG_PWD || 'Demo#2026'

const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1760, height: 1000 } }).then((c) => c.newPage())
const errs = []
page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 140)))

const R = []
const ok = (name, pass, detail = '') => {
  R.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}
const skip = (name, why) => {
  R.push({ name, pass: true, skip: true })
  console.log(`SKIP | ${name} — ${why}`)
}

/**
 * 切换侧边栏菜单，并等待目标页面「真的渲染出来」。
 * 原先用固定 waitForTimeout，在线上（跨网络）偶尔不够，会把上一页的内容
 * 当成结果读走，造成假失败。这里改为等页面特征文案出现。
 */
const MENU_PATH = {
  经营驾驶舱: '/dashboard',
  任务管理: '/tasks',
  指标维护: '/metrics',
  账号管理: '/accounts',
}

/**
 * 切换侧边栏菜单。
 *
 * 教训：不能只等「页面里出现某个元素」——驾驶舱与任务页都有 <table>，
 * 路由还没切完时 main thead th 会先匹配到上一页的表格，于是读到错的数据。
 * 因此第一步先等 URL 真正切到目标路由，再等页面元素。
 */
async function gotoMenu(label, marker = '', selector = '') {
  const expect = MENU_PATH[label]
  await page.click(`aside nav a:has-text("${label}")`)
  if (expect) {
    const routed = await page
      .waitForFunction((p) => location.pathname.startsWith(p), expect, { timeout: 15000 })
      .then(() => true)
      .catch(() => false)
    if (!routed) console.log(`  [导航] 未切到 ${expect}，当前 ${page.url()}`)
  }
  if (selector) {
    await page.locator(selector).last().waitFor({ state: 'visible', timeout: 15000 }).catch(() => {})
  }
  if (marker) {
    // 标记必须是目标页面独有的文案，否则会立即通过、读到上一页内容
    const settled = await page
      .waitForFunction(
        (m) => (document.querySelector('main')?.innerText || '').includes(m),
        marker,
        { timeout: 15000 },
      )
      .then(() => true)
      .catch(() => false)
    if (!settled) console.log(`  [导航] 未等到「${label}」渲染（标记：${marker}），当前 URL=${page.url()}`)
  }
  await page.waitForTimeout(400)
}

/**
 * 等「任务管理」的表格真正就绪。
 * 驾驶舱页同样有 <table>（6 列），任务表是 14 列；且任务页是工具栏先出、表格后到。
 * 故以列数 >= 10 作为「任务表已渲染」的判据，避免读到上一页或空表。
 */
async function waitForTaskTable() {
  await page
    .waitForFunction(() => document.querySelectorAll('main thead th').length >= 10, null, { timeout: 15000 })
    .catch(() => {})
}

await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.fill('input[type="text"], input:not([type])', 'chenzm').catch(() => {})
const pw = page.locator('input[type="password"]')
if (await pw.count()) {
  await pw.fill(PWD)
  await page.click('button[type="submit"], button:has-text("登录")')
}
await page.waitForTimeout(4500)
console.log('URL:', page.url(), '\n')

// ---------------- 1 统计周期 ----------------
console.log('──── 1. 统计周期 ────')
const headerHasPeriod = await page.evaluate(() => {
  const h = document.querySelector('header')
  return !!(h && /统计周期/.test(h.innerText))
})
ok('顶栏不再显示统计周期', !headerHasPeriod)

await gotoMenu('经营驾驶舱', '核心指标')
const dashPicker = await page.evaluate(() => {
  const btns = [...document.querySelectorAll('main button[aria-haspopup="dialog"]')]
  return btns.length ? { n: btns.length, text: btns[0].innerText.trim() } : null
})
ok('驾驶舱内展示统计周期', !!dashPicker, dashPicker ? `触发器=${dashPicker.text}` : '未找到')
ok('统计周期为面板式月份选择器', /^\d{4}年\d{1,2}月$/.test(dashPicker?.text || ''), dashPicker?.text || '')
ok('不再使用原生 type=month 输入框', (await page.locator('main input[type="month"]').count()) === 0)

await gotoMenu('指标维护', '公司整体目标')
const metricPicker = await page.evaluate(() =>
  [...document.querySelectorAll('main button[aria-haspopup="dialog"]')].map((e) => e.innerText.trim()),
)
ok('指标维护内展示统计周期', metricPicker.length > 0, JSON.stringify(metricPicker[0] ?? ''))

await gotoMenu('任务管理', '按部门分组')
await waitForTaskTable()
const taskHasPeriod = await page.evaluate(() => {
  const h = document.querySelector('header')
  return (
    !!(h && /统计周期/.test(h.innerText)) ||
    document.querySelectorAll('main button[aria-haspopup="dialog"]').length > 0
  )
})
ok('任务管理不显示统计周期', !taskHasPeriod)

// 选到 2099-12 边界不报错
await gotoMenu('经营驾驶舱', '核心指标')
// 走面板真实交互：年份跳转 → 选 2099 → 选 12 月
const boundary = await page.evaluate(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const trigger = document.querySelector('main button[aria-haspopup="dialog"]')
  if (!trigger) return { ok: false, reason: 'no trigger' }
  trigger.click()
  await sleep(400)
  const panel = document.querySelector('[role="dialog"][aria-label="选择统计周期"]')
  if (!panel) return { ok: false, reason: 'panel not open' }

  const title = [...panel.querySelectorAll('button')].find((b) => /^\d{4}年$/.test(b.innerText.trim()))
  if (!title) return { ok: false, reason: 'no year title' }
  title.click()
  await sleep(300)

  let guard = 0
  while (guard++ < 12) {
    const years = [...panel.querySelectorAll('button')]
      .map((b) => b.innerText.trim())
      .filter((t) => /^\d{4}$/.test(t))
    if (years.includes('2099')) break
    const next = [...panel.querySelectorAll('button')].find((b) => (b.getAttribute('aria-label') || '') === '下一页')
    if (!next || next.disabled) return { ok: false, reason: '无法翻到 2099' }
    next.click()
    await sleep(250)
  }

  const y2099 = [...panel.querySelectorAll('button')].find((b) => b.innerText.trim() === '2099')
  if (!y2099) return { ok: false, reason: '未找到 2099' }
  y2099.click()
  await sleep(300)

  const dec = [...panel.querySelectorAll('button')].find((b) => b.innerText.trim() === '12月')
  if (!dec) return { ok: false, reason: '未找到 12月' }
  dec.click()
  await sleep(2200)

  const label = document.querySelector('main button[aria-haspopup="dialog"]')?.innerText.trim()
  return {
    ok: !document.body.innerText.includes('加载失败') && label === '2099年12月',
    label,
    reason: label === '2099年12月' ? '' : `触发器=${label}`,
  }
})
ok('可选到 2099-12 且不报错', boundary.ok, boundary.reason || `触发器=${boundary.label}`)

// ---------------- 2 累计完成值 ----------------
console.log('\n──── 2. 累计完成值口径 ────')
await gotoMenu('指标维护', '公司整体目标')
const culm = await page.evaluate(() => {
  const t = document.body.innerText
  return { hasCulm: /累计完成值/.test(t), hasOld: /完成值为年初至今累计/.test(t) }
})
ok('指标维护出现「累计完成值」', culm.hasCulm)
ok('旧文案已移除', !culm.hasOld)
const projCol = await page.evaluate(() => /累计完成/.test(document.body.innerText))
ok('项目公司列为「累计完成」', projCol)

await gotoMenu('经营驾驶舱', '核心指标')
const dashCulm = await page.evaluate(() => /累计完成值/.test(document.body.innerText) && !/完成值为年初至今累计/.test(document.body.innerText))
ok('驾驶舱文案已同步', dashCulm)

// ---------------- 3 任务管理 ----------------
console.log('\n──── 3. 任务管理 ────')
await gotoMenu('任务管理', '按部门分组')
await waitForTaskTable()
// 演示环境的任务数据可能已被清空，此时整张表都不渲染（显示「暂无任务」），
// 依赖表头与行内容的断言不适用 —— 明确跳过，避免把空态误判成功能异常。
const taskTotal = await page.evaluate(() => {
  const m = /共\s*(\d+)\s*项任务/.exec(document.body.innerText)
  return m ? Number(m[1]) : -1
})
if (taskTotal === 0) {
  skip('任务管理列与分组视图（创建时间 / 更新时间 / 创建人 / 分组小标题）', '当前任务数据为 0 条，表格处于空态')
} else {
  const head = await page.evaluate(() => [...document.querySelectorAll('main thead th')].map((e) => e.innerText.trim()))
  ok('含「创建时间」列', head.includes('创建时间'), head.join('/'))
  ok('含「更新时间」列', head.includes('更新时间'))

  const times = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('main tbody tr')].filter((r) => r.querySelector('td .font-mono'))
    return rows.slice(0, 2).map((r) => {
      const tds = [...r.querySelectorAll('td')].map((td) => td.innerText.trim())
      return tds.slice(9, 11)
    })
  })
  ok('时间列有值且格式可读', times.every((t) => t.length === 2 && /\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(t[0])), JSON.stringify(times))

  // 分组视图
  const groupBtn = page.locator('main button:has-text("按部门分组")')
  ok('存在「按部门分组」切换', (await groupBtn.count()) > 0)
  if (await groupBtn.count()) {
    await groupBtn.first().click()
    await page.waitForTimeout(900)
    const g = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('main tbody tr')]
      const headers = rows.filter((r) => r.querySelectorAll('td').length === 1)
      return {
        headerCount: headers.length,
        samples: headers.slice(0, 4).map((r) => r.innerText.replace(/\s+/g, ' ').trim()),
        colspan: headers[0]?.querySelector('td')?.getAttribute('colspan'),
        colCount: document.querySelectorAll('main thead th').length,
      }
    })
    ok('分组视图出现部门小标题', g.headerCount > 0, `${g.headerCount} 组，示例：${g.samples.join(' | ')}`)
    ok('小标题整行跨列', String(g.colspan) === String(g.colCount), `colspan=${g.colspan} 列数=${g.colCount}`)
    await page.screenshot({ path: '/tmp/verify-grouped.png', fullPage: true })
  }
}

// ---------------- 4 权限可配置 ----------------
console.log('\n──── 4. 权限可配置 ────')
await gotoMenu('账号管理', '角色权限')
// 角色表单在「角色权限」标签页内，需先切标签
await page.click('main button:has-text("角色权限")').catch(() => {})
await page.waitForTimeout(2000)
const roleForm = await page.evaluate(async () => {
  const btn = [...document.querySelectorAll('main button')].find((b) => b.innerText.includes('新增角色'))
  if (btn) btn.click()
  await new Promise((r) => setTimeout(r, 1200))
  const text = document.body.innerText
  return {
    opened: /新增角色|编辑角色/.test(text),
    hasCompanyPerm: /维护公司整体目标/.test(text),
    hasProjectPerm: /维护项目公司指标/.test(text),
    hasSystemToggle: /标记为内置角色/.test(text),
  }
})
ok('角色表单含新权限项「维护公司整体目标」', roleForm.hasCompanyPerm)
ok('角色表单含新权限项「维护项目公司指标」', roleForm.hasProjectPerm)
ok('内置标记可配置', roleForm.hasSystemToggle)
// 弹窗自带全屏遮罩，必须点「取消」关闭，否则遮罩会挡住后续点击
await page.click('button:has-text("取消")').catch(() => {})
await page.waitForTimeout(900)

await gotoMenu('指标维护', '公司整体目标')
// 数据范围不再可切换：管理员固定为全公司范围，因此不会出现「部门数据范围」说明条
// （该说明条只在部门范围的账号下显示）。这里验证：说明条按条件收敛、且文案不写死角色名。
const scopeHint = await page.evaluate(() => {
  const t = (document.querySelector('main')?.innerText || '').replace(/\s+/g, '')
  return {
    shown: /当前数据范围为你所属的部门/.test(t),
    writesRole: /(系统管理员|部门负责人|普通成员)/.test(t),
  }
})
ok('全公司数据范围下不显示部门范围说明条', !scopeHint.shown)
ok('权限相关文案不写死角色名', !scopeHint.writesRole)

// ---------------- 5. 本轮：模板一致性与入口调整 ----------------
console.log('\n──── 5. 任务字段一致性 / 模板入口 ────')
await gotoMenu('任务管理', '按部门分组')
await waitForTaskTable()
const t2 = await page.evaluate(() => {
  const head = [...document.querySelectorAll('main thead th')].map((e) => e.innerText.trim())
  const creatorIdx = head.indexOf('创建人')
  const rows = [...document.querySelectorAll('main tbody tr')].filter((r) => r.querySelectorAll('td').length > 3)
  const vals = rows.slice(0, 5).map((r) => [...r.querySelectorAll('td')][creatorIdx]?.innerText.trim())
  const btnTexts = [...document.querySelectorAll('main button, main label')].map((b) => b.innerText.trim())
  return { head, creatorIdx, vals, btnTexts }
})
if (t2.head.length === 0) {
  // 任务数据为空时整张表不渲染，列相关断言不适用
  skip('列表含「创建人」列', '当前任务数据为 0 条，表格未渲染')
  skip('创建人列有值', '同上')
} else {
  ok('列表含「创建人」列', t2.creatorIdx >= 0, t2.head.join('/'))
  ok('创建人列有值', t2.vals.some((v) => v && v !== '—'), JSON.stringify(t2.vals))
}
ok('任务管理保留「下载模板」', t2.btnTexts.some((b) => b.includes('下载模板')))
ok('任务管理保留「导出」', t2.btnTexts.some((b) => b.includes('导出')))

const tpl = await page.evaluate(async () => {
  const r = await fetch('/api/v1/tasks/import/template', { credentials: 'include' })
  const b = await r.blob()
  return { status: r.status, size: b.size }
})
ok('任务导入模板可下载', tpl.status === 200 && tpl.size > 0, `status=${tpl.status} size=${tpl.size}`)

const exp = await page.evaluate(async () => {
  const r = await fetch('/api/v1/tasks/export', { credentials: 'include' })
  const b = await r.blob()
  return { status: r.status, size: b.size }
})
ok('任务导出文件可下载', exp.status === 200 && exp.size > 0, `status=${exp.status} size=${exp.size}`)

await gotoMenu('指标维护', '公司整体目标')
const mBtns = await page.evaluate(() =>
  [...document.querySelectorAll('main button, main label')].map((b) => b.innerText.trim()),
)
ok('指标维护已移除「下载模板」', !mBtns.some((b) => b.includes('下载模板')), mBtns.join(' | '))
ok('指标维护已移除「批量导入」', !mBtns.some((b) => b.includes('批量导入')))
ok('指标维护保留「查看驾驶舱」', mBtns.some((b) => b.includes('查看驾驶舱')))

console.log('\n控制台错误：', errs.length ? errs.join(' / ') : '0 个 ✅')
const pass = R.filter((r) => r.pass).length
const skips = R.filter((r) => r.skip).length
console.log(`\n===== 汇总：${pass}/${R.length} 通过${skips ? `（含 ${skips} 项因数据为空跳过）` : ''} =====`)
if (R.some((r) => !r.pass)) {
  console.log('失败明细：')
  for (const f of R.filter((r) => !r.pass)) console.log(` - ${f.name} ${f.detail}`)
}
await browser.close()
process.exit(R.some((r) => !r.pass) ? 1 : 0)
