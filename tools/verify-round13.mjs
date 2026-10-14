/**
 * 第十三轮浏览器验收 · 账号模块三项改动
 *
 * 用法：BASE_URL=http://127.0.0.1:8000 DIAG_USER=admin DIAG_PWD=123456 node verify-round13.mjs
 * 前置：XLSX_PATH 指向待导入的模板文件。
 */
import pw from '/Users/gavin/.workbuddy/binaries/node/workspace/node_modules/playwright-core/index.js'
import { execFileSync } from 'node:child_process'
const { chromium } = pw

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const USER = process.env.DIAG_USER || 'admin'
const PWD = process.env.DIAG_PWD || '123456'
const XLSX = process.env.XLSX_PATH || '/tmp/verify13_accounts.xlsx'

/** 每次跑都换一批账号名：批量导入对同名账号会判重，固定文件名重复跑必然失败 */
const SUFFIX = String(Date.now()).slice(-7)
const ACCT_A = 'imp' + SUFFIX + 'a'
const ACCT_B = 'imp' + SUFFIX + 'b'

const GEN = `
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Sheet"
ws.append(["账号批量导入标准模板"])
ws.append([])
ws.append([])
ws.append(["姓名", "账号", "初始密码", "所属部门", "角色", "数据可见范围", "状态"])
ws.append(["导入甲", "${ACCT_A}", "Pass#2026", "市场部", "普通成员", "全公司", "启用"])
ws.append(["导入乙", "${ACCT_B}", "Pass#2026", "市场部", "普通成员", "本部门", ""])
wb.save("${XLSX}")
`
execFileSync('backend/.venv/bin/python', ['-c', GEN], { stdio: 'inherit' })

let passed = 0
let failed = 0
const errs = []

function ok(name, cond, extra = '') {
  if (cond) {
    passed++
    console.log('  OK ' + name + (extra ? ' (' + extra + ')' : ''))
  } else {
    failed++
    console.log('  NG ' + name + (extra ? ' (' + extra + ')' : ''))
  }
}

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } })
const page = await ctx.newPage()
const httpErrs = []
page.on('console', (m) => {
  if (m.type() === 'error') {
    const loc = m.location()
    errs.push(m.text() + ' @ ' + (loc && loc.url ? loc.url : '?'))
  }
})
page.on('pageerror', (e) => errs.push(String(e)))
page.on('response', (r) => {
  if (r.status() >= 400) httpErrs.push('HTTP ' + r.status() + ' ' + r.url())
})

await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
await page.fill('input[type="text"], input:not([type])', USER)
await page.fill('input[type="password"]', PWD)
await page.click('button[type="submit"]')
await page.waitForURL('**/dashboard', { timeout: 20000 })
await page.waitForTimeout(1800)

const api = (path, opts = {}) =>
  page.evaluate(
    async ([p, o]) => {
      const r = await fetch(p, { credentials: 'include', ...o })
      const t = await r.text()
      try {
        return { status: r.status, body: JSON.parse(t) }
      } catch {
        return { status: r.status, body: t }
      }
    },
    [BASE + path, opts],
  )

// =============================================== 一、可见范围必选
console.log('\n一、数据可见范围必须人工选择')

await page.goto(BASE + '/accounts', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

await page.click('button:has-text("新增账号")')
await page.waitForTimeout(600)

// 注意：不能按「全公司」文本找下拉 —— 组织清单里也有名为「全公司」的公司节点。
// 只有可见范围下拉含 value="all"，用它唯一定位。
const scopeSel = page.locator('select:has(option[value="all"])')
const scopeOpts = await scopeSel
  .first()
  .evaluate((s) => [...s.options].map((o) => o.textContent.trim()))
  .catch(() => null)
ok('可见范围下拉存在', !!scopeOpts)
ok(
  '不再包含「跟随角色默认」选项',
  !!scopeOpts && !scopeOpts.some((t) => /跟随角色默认/.test(t)),
  scopeOpts ? scopeOpts.join(' / ') : '',
)
ok(
  '保留四档可选范围',
  !!scopeOpts &&
    ['本人', '本部门', '本部门及下属部门', '全公司'].every((t) => scopeOpts.includes(t)),
)

// 不选范围直接保存 → 应被前端拦下
await page.fill('input[placeholder*="姓名"]', '验收脚本员')
await page.fill('input[placeholder*="登录账号"]', 'verify13a')
await page.fill('input[type="password"]', 'Pass#2026')
await page.click('button:has-text("保存")')
await page.waitForTimeout(700)
const blocked = await page.evaluate(() => /请选择数据可见范围/.test(document.body.innerText))
ok('未选范围时拒绝保存并提示', blocked)

await page.keyboard.press('Escape')
await page.waitForTimeout(300)

// =============================================== 二、批量导入
console.log('\n二、批量导入账号')

// 模板接口要求登录态，必须走页面内 fetch 才能带上会话 Cookie
const tpl = await page.evaluate(async (u) => {
  const r = await fetch(u, { credentials: 'include' })
  const b = await r.arrayBuffer()
  return { status: r.status, bytes: b.byteLength, type: r.headers.get('content-type') || '' }
}, BASE + '/api/v1/users/import/template')
ok(
  '导入模板接口可达且返回文件',
  tpl.status === 200 && tpl.bytes > 1000,
  'HTTP ' + tpl.status + ' ' + tpl.bytes + 'B ' + tpl.type,
)

const before = await api('/api/v1/users')
ok('账号列表可读取', Array.isArray(before.body), 'count=' + (before.body ? before.body.length : '?'))

await page.click('button:has-text("批量导入")')
await page.waitForTimeout(600)
const hasTplBtn = await page.locator('button:has-text("下载模板")').first().isVisible()
ok('导入弹窗含「下载模板」按钮', hasTplBtn)

await page.setInputFiles('input[type="file"]', XLSX)
await page.waitForTimeout(400)
await page.click('button:has-text("开始导入")')
await page.waitForTimeout(2500)

const importedMsg = await page.evaluate(() => {
  const m = document.body.innerText.match(/成功导入\s*\d+\s*个账号/)
  return m ? m[0] : null
})
ok('导入回执显示成功条数', !!importedMsg, importedMsg || 'no receipt')

await page.screenshot({ path: '/tmp/verify13_import.png' })
await page.keyboard.press('Escape')
await page.waitForTimeout(300)

// ============================================================ 三、删除
console.log('\n三、删除账号的引用检查')

const after = await api('/api/v1/users')
const byAcct = Object.fromEntries(after.body.map((u) => [u.account, u]))

const clean = byAcct[ACCT_A]
const busy = byAcct[ACCT_B]
ok('导入的两个账号都已入库', !!clean && !!busy, ACCT_A + ' / ' + ACCT_B)
ok('状态留空默认启用', !!busy && busy.status === 'active', busy ? busy.status : '')

// 造一个引用：把某条任务的责任人改成 B 的姓名；库里没任务就先建一条
let tid = null
let tempTid = null
const first = await api('/api/v1/tasks?size=1')
tid = first.body.items && first.body.items[0] && first.body.items[0].id
if (!tid && busy) {
  const created = await api('/api/v1/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      parent: '验收临时任务',
      title: '验收',
      target: 100,
      done: 0,
      unit: '个',
      start_date: '2026-01-01',
      end_date: '2026-12-31',
      dept_id: 'D01',
      owner: '占位',
    }),
  })
  tid = created.body && created.body.id
  tempTid = tid
}

if (busy && tid) {
  // TaskUpdate 全量字段必填且是 snake_case，而 GET 回的是 camelCase，
  // 不能直接展开回传 —— 必须显式逐字段构造，否则会缺 start_date 等被 422 拒。
  const cur = (await api('/api/v1/tasks/' + tid)).body || {}
  const full = {
    parent: cur.parent,
    title: cur.title ?? '',
    description: cur.description ?? '',
    abnormal: !!cur.abnormal,
    target: cur.target,
    done: cur.done,
    unit: cur.unit ?? '',
    note: cur.note ?? '',
    start_date: cur.startDate,
    end_date: cur.endDate,
    dept_id: cur.deptId,
    owner: busy.name,
  }
  const patched = await api('/api/v1/tasks/' + tid, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(full),
  })
  ok(
    '责任人改为待删账号',
    patched.status === 200 && patched.body.owner === busy.name,
    'HTTP ' + patched.status + ' owner=' + (patched.body.owner || '-'),
  )
  const imp2 = await api('/api/v1/users/' + busy.id + '/impact')
  ok(
    '被选为责任人后引用数 > 0',
    !!imp2.body && (imp2.body.taskOwner || 0) >= 1,
    JSON.stringify(imp2.body),
  )
  const del2 = await api('/api/v1/users/' + busy.id, { method: 'DELETE' })
  ok(
    '被引用时拒绝删除',
    del2.status === 409,
    'HTTP ' + del2.status + ' ' + ((del2.body && del2.body.detail) || ''),
  )
}

if (clean) {
  const imp1 = await api('/api/v1/users/' + clean.id + '/impact')
  ok('无引用时预检全为 0', !!imp1.body && Object.values(imp1.body).every((v) => v === 0 || v === false), JSON.stringify(imp1.body))
  const del1 = await api('/api/v1/users/' + clean.id, { method: 'DELETE' })
  ok('未被引用的账号可删除', del1.status === 200, 'HTTP ' + del1.status + ' ' + ((del1.body && del1.body.detail) || ''))
  const left = await api('/api/v1/users')
  ok('删除后库中查不到', !left.body.some((u) => u.id === clean.id))
}

// 兜底清理：临时任务先删，再删账号；已删的不重复删，避免制造无意义的 404
if (tempTid) await api('/api/v1/tasks/' + tempTid, { method: 'DELETE' })
const rest = await api('/api/v1/users')
const alive = new Set((rest.body || []).map((u) => u.id))
for (const u of [busy, clean]) {
  if (u && alive.has(u.id)) await api('/api/v1/users/' + u.id, { method: 'DELETE' })
}

// 409 / 422 是本轮刻意触发的（拒绝删除、缺字段），其余 4xx/5xx 才需要排查
const realHttp = httpErrs.filter((e) => !/HTTP (409|422) /.test(e))
console.log('\n控制台错误：' + errs.length + ' 个' + (errs.length ? ' NG' : ' OK'))
if (errs.length) errs.slice(0, 5).forEach((e) => console.log('   -', e))
console.log('非预期 HTTP 错误：' + realHttp.length + ' 个' + (realHttp.length ? ' NG' : ' OK'))
if (realHttp.length) realHttp.slice(0, 8).forEach((e) => console.log('   -', e))
console.log('\n结果：' + passed + ' 通过，' + failed + ' 失败')

await browser.close()
process.exit(failed ? 1 : 0)
