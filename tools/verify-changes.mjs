/**
 * 本轮四项需求验收（真实浏览器）。
 * 1 统计周期：顶栏无 / 驾驶舱有 / 指标维护有 / 任务管理无，且为月份组件、范围受限
 * 2 累计完成值文案
 * 3 任务管理：创建时间 + 更新时间列；按部门分组视图带小标题
 * 4 权限说明文案（不写死角色）
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const PWD = 'Demo#2026'

const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1760, height: 1000 } }).then((c) => c.newPage())
const errs = []
page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 140)))

const R = []
const ok = (name, pass, detail = '') => {
  R.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}

async function gotoMenu(label) {
  await page.click(`aside nav a:has-text("${label}")`)
  await page.waitForTimeout(2200)
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

await gotoMenu('经营驾驶舱')
const dashPicker = await page.evaluate(() => {
  const el = [...document.querySelectorAll('main input[type="month"]')]
  return el.length
    ? { n: el.length, min: el[0].min, max: el[0].max, value: el[0].value }
    : null
})
ok('驾驶舱内展示统计周期', !!dashPicker, dashPicker ? `min=${dashPicker.min} max=${dashPicker.max} value=${dashPicker.value}` : '未找到')
ok('驾驶舱为月份选择组件', dashPicker?.min === '2026-09' && dashPicker?.max === '2099-12', dashPicker ? `范围 ${dashPicker.min} ~ ${dashPicker.max}` : '')
ok('默认可选起点为 2026-09', dashPicker?.min === '2026-09')

await gotoMenu('指标维护')
const metricPicker = await page.evaluate(() =>
  [...document.querySelectorAll('main input[type="month"]')].map((e) => ({ min: e.min, max: e.max, value: e.value })),
)
ok('指标维护内展示统计周期', metricPicker.length > 0, JSON.stringify(metricPicker[0] ?? {}))

await gotoMenu('任务管理')
const taskHasPeriod = await page.evaluate(() => {
  const h = document.querySelector('header')
  const body = document.body.innerText
  return !!(h && /统计周期/.test(h.innerText)) || (/统计周期/.test(body) && document.querySelectorAll('main input[type="month"]').length > 0)
})
ok('任务管理不显示统计周期', !taskHasPeriod)

// 选到 2099-12 边界不报错
await gotoMenu('经营驾驶舱')
const boundary = await page.evaluate(async () => {
  const el = document.querySelector('main input[type="month"]')
  if (!el) return { ok: false, reason: 'no input' }
  el.value = '2099-12'
  el.dispatchEvent(new Event('change', { bubbles: true }))
  await new Promise((r) => setTimeout(r, 2500))
  return { ok: !document.body.innerText.includes('加载失败'), text: document.body.innerText.slice(0, 80) }
})
ok('可选到 2099-12 且不报错', boundary.ok, boundary.reason || '')

// ---------------- 2 累计完成值 ----------------
console.log('\n──── 2. 累计完成值口径 ────')
await gotoMenu('指标维护')
const culm = await page.evaluate(() => {
  const t = document.body.innerText
  return { hasCulm: /累计完成值/.test(t), hasOld: /完成值为年初至今累计/.test(t) }
})
ok('指标维护出现「累计完成值」', culm.hasCulm)
ok('旧文案已移除', !culm.hasOld)
const projCol = await page.evaluate(() => /累计完成/.test(document.body.innerText))
ok('项目公司列为「累计完成」', projCol)

await gotoMenu('经营驾驶舱')
const dashCulm = await page.evaluate(() => /累计完成值/.test(document.body.innerText) && !/完成值为年初至今累计/.test(document.body.innerText))
ok('驾驶舱文案已同步', dashCulm)

// ---------------- 3 任务管理 ----------------
console.log('\n──── 3. 任务管理 ────')
await gotoMenu('任务管理')
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

// ---------------- 4 权限可配置 ----------------
console.log('\n──── 4. 权限可配置 ────')
await gotoMenu('账号管理')
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

await gotoMenu('指标维护')
// 说明条仅在非「全公司」视角下展示，需先切到项目公司视角
const orgSel = page.locator('header select').first()
if (await orgSel.count()) {
  const opt = await page.evaluate(
    () => [...document.querySelectorAll('header select option')].map((o) => o.value).find((v) => v.startsWith('PC')) || '',
  )
  if (opt) {
    await orgSel.selectOption(opt)
    await page.waitForTimeout(2500)
  }
}
const gate = await page.evaluate(() =>
  /能否维护只看权限/.test(document.body.innerText.replace(/\s+/g, '')),
)
ok('指标维护权限说明不再写死角色', gate, `组织视角=${await page.evaluate(() => document.querySelector('header select')?.value)}`)

// ---------------- 5. 本轮：模板一致性与入口调整 ----------------
console.log('\n──── 5. 任务字段一致性 / 模板入口 ────')
await gotoMenu('任务管理')
const t2 = await page.evaluate(() => {
  const head = [...document.querySelectorAll('main thead th')].map((e) => e.innerText.trim())
  const creatorIdx = head.indexOf('创建人')
  const rows = [...document.querySelectorAll('main tbody tr')].filter((r) => r.querySelectorAll('td').length > 3)
  const vals = rows.slice(0, 5).map((r) => [...r.querySelectorAll('td')][creatorIdx]?.innerText.trim())
  const btnTexts = [...document.querySelectorAll('main button, main label')].map((b) => b.innerText.trim())
  return { head, creatorIdx, vals, btnTexts }
})
ok('列表含「创建人」列', t2.creatorIdx >= 0, t2.head.join('/'))
ok('创建人列有值', t2.vals.some((v) => v && v !== '—'), JSON.stringify(t2.vals))
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

await gotoMenu('指标维护')
const mBtns = await page.evaluate(() =>
  [...document.querySelectorAll('main button, main label')].map((b) => b.innerText.trim()),
)
ok('指标维护已移除「下载模板」', !mBtns.some((b) => b.includes('下载模板')), mBtns.join(' | '))
ok('指标维护已移除「批量导入」', !mBtns.some((b) => b.includes('批量导入')))
ok('指标维护保留「查看驾驶舱」', mBtns.some((b) => b.includes('查看驾驶舱')))

console.log('\n控制台错误：', errs.length ? errs.join(' / ') : '0 个 ✅')
const pass = R.filter((r) => r.pass).length
console.log(`\n===== 汇总：${pass}/${R.length} 通过 =====`)
if (R.some((r) => !r.pass)) {
  console.log('失败明细：')
  for (const f of R.filter((r) => !r.pass)) console.log(` - ${f.name} ${f.detail}`)
}
await browser.close()
process.exit(R.some((r) => !r.pass) ? 1 : 0)
