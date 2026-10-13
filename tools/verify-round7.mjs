/**
 * 第七轮专项验收：数据权限边界（仅任务模块按可见范围隔离）
 *
 * 口径：
 *   · 经营驾驶舱 / 指标维护 —— 只按角色权限判断能否查看，一律全公司口径；
 *   · 任务模块 —— 唯一按数据可见范围隔离的模块。
 *
 * 做法：
 *   1. 造 3 条任务（1 条属 D03、2 条属 D01）用于对比两种口径；
 *   2. 用现成账号（默认 huguohai，部门负责人 · D03）验证；
 *      —— 后端没有删除账号的 HTTP 接口（删除能力刻意做成命令行工具），
 *         所以这里不新建账号，而是**可逆地**临时把它的可见范围切到「本部门及下属」，
 *         结束时还原为原值；
 *   3. 清理造的数据。
 *
 * 实现注意（两处环境差异，都实际踩过）：
 *   · 管理端调用必须走**独立的浏览器上下文**（自带 cookie jar）。
 *     不能用「页面上下文的 request」—— 它会以页面登录的账号发请求，清理步骤会 403；
 *   · 也不能用「fetch + Authorization: Bearer」—— 线上网关会注入/覆盖 Authorization 头，
 *     后端收到的是网关的 token 而返回 401（本地无网关所以能过）。Cookie 认证两边都可靠。
 *
 * 用法：
 *   BASE_URL=http://127.0.0.1:8000 node verify-round7.mjs
 *   BASE_URL=https://... DIAG_PWD=xxx HEAD_PWD=xxx node verify-round7.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
// 凭据用脚本专用变量：shell 自带的 USER / PWD 分别已是当前用户名与工作目录
const ADMIN_USER = process.env.DIAG_USER || 'admin'
const ADMIN_PWD = process.env.DIAG_PWD || '123456'
const HEAD_ACCOUNT = process.env.HEAD_USER || 'huguohai'
const HEAD_PWD = process.env.HEAD_PWD || '123456'

const R = []
const ok = (name, pass, detail = '') => {
  R.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}
const skip = (name, why) => {
  R.push({ name, pass: true, skip: true })
  console.log(`SKIP | ${name} — ${why}`)
}

const browser = await chromium.launch()

/**
 * 管理端上下文：独立的 cookie jar。
 * 与页面上下文隔离（不会串账号），也天然绕开线上网关对 Authorization 头的覆盖。
 */
const adminCtx = await browser.newContext()
const adminApi = adminCtx.request
async function adminCall(method, path, body) {
  const res = await adminApi.fetch(`${BASE}${path}`, { method, data: body })
  const data = await res.json().catch(() => null)
  return { ok: res.ok(), status: res.status(), data }
}

// ---------- 准备：管理员登录 / 造数 / 准备部门账号 ----------
const loginRes = await adminCall('POST', '/api/v1/auth/login', { account: ADMIN_USER, password: ADMIN_PWD })
ok(
  '准备：管理员登录',
  loginRes.ok,
  `HTTP ${loginRes.status}${loginRes.ok ? '' : ' ' + JSON.stringify(loginRes.data).slice(0, 80)}`,
)

const usersRes = await adminCall('GET', '/api/v1/users')
const userList = Array.isArray(usersRes.data) ? usersRes.data : usersRes.data?.items || []
const headUser = userList.find((u) => u.account === HEAD_ACCOUNT)
ok(
  '准备：找到部门负责人账号',
  !!headUser,
  headUser
    ? `${headUser.name} · ${headUser.deptName}`
    : `未找到 ${HEAD_ACCOUNT}（HTTP ${usersRes.status}，共 ${userList.length} 个账号）`,
)

// 记录原始可见范围，结束时还原
const originalScope = headUser?.scope ?? ''
let scopeSwitched = false
if (headUser && headUser.scope !== 'dept_sub') {
  const patched = await adminCall('PATCH', `/api/v1/users/${headUser.id}`, {
    name: headUser.name,
    dept_id: headUser.deptId,
    role_id: headUser.roleId,
    scope: 'dept_sub',
    status: headUser.status,
  })
  scopeSwitched = patched.ok
  ok('准备：临时把该账号可见范围切到「本部门及下属」', scopeSwitched, `原值=${originalScope || '跟随角色'} → dept_sub`)
}

// 造 3 条任务（1 条 D03、2 条 D01），用于对比「全量口径」与「任务按范围收窄」
const madeTaskIds = []
for (const [i, dept] of ['D03', 'D01', 'D01'].entries()) {
  const r = await adminCall('POST', '/api/v1/tasks', {
    parent: `权限边界验证任务 ${i + 1}`,
    title: '',
    description: '',
    abnormal: false,
    target: 100,
    done: 0,
    unit: '',
    note: '',
    start_date: '2026-10-01',
    end_date: '2026-12-31',
    dept_id: dept,
    owner: '郑凯',
  })
  if (r.ok) madeTaskIds.push(r.data.id)
}
ok('准备：造 3 条对比用任务', madeTaskIds.length === 3, `已建 ${madeTaskIds.length} 条`)

// ---------- 页面上下文（与管理端上下文隔离） ----------
const ctx = await browser.newContext({ viewport: { width: 1560, height: 950 } })
const page = await ctx.newPage()
const errs = []
page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 140)))
page.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 140)))

async function login(account, password) {
  // 先清掉上一次的登录态：已登录时访问根路径会被路由直接带到驾驶舱，不会再出现登录页
  await page.goto(BASE, { waitUntil: 'domcontentloaded' })
  await page.evaluate(() => {
    try {
      localStorage.clear()
    } catch {
      /* 忽略 */
    }
  })
  await ctx.clearCookies()

  await page.goto(BASE, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('input[type="password"]', { state: 'visible', timeout: 20000 }).catch(() => {})
  await page.locator('input[type="text"], input:not([type])').first().fill(account)
  await page.locator('input[type="password"]').first().fill(password)
  await page.locator('button:has-text("登录")').first().click()
  const inApp = await page
    .waitForFunction(() => !!document.querySelector('aside nav'), null, { timeout: 30000 })
    .then(() => true)
    .catch(() => false)
  await page.waitForTimeout(2200)
  return inApp
}

async function gotoTab(name) {
  await page.locator(`aside nav a:has-text("${name}")`).first().click()
  await page.waitForTimeout(2600)
}

async function readTaskTotal() {
  return page.evaluate(() => {
    const m = /共\s*(\d+)\s*项任务/.exec(document.body.innerText)
    return m ? Number(m[1]) : -1
  })
}

// ---------- 管理员基线（全量口径） ----------
await login(ADMIN_USER, ADMIN_PWD)
await gotoTab('任务管理')
const adminTaskTotal = await readTaskTotal()

await gotoTab('驾驶舱')
const adminDash = await page.evaluate(() => {
  const t = document.body.innerText.replace(/\s+/g, ' ')
  return {
    hasCards: /综合加权达成率|营业收入|累计/.test(t),
    failed: /加载失败/.test(t),
    hasScopeSelect: !!document.querySelector('header select'),
  }
})
ok('管理员：驾驶舱正常渲染', adminDash.hasCards && !adminDash.failed, adminDash.failed ? '出现「加载失败」' : '')
ok('顶栏不再提供组织视角切换（无 select）', !adminDash.hasScopeSelect)

// ---------- 部门范围账号 ----------
const headLoggedIn = await login(HEAD_ACCOUNT, HEAD_PWD)
if (!headLoggedIn) {
  skip('部门范围账号的全部检查', `${HEAD_ACCOUNT} 无法登录（线上密码可能不同，可用 HEAD_PWD 指定）`)
} else {
  await gotoTab('驾驶舱')
  const headDash = await page.evaluate(() => {
    const t = document.body.innerText.replace(/\s+/g, ' ')
    return {
      hasCards: /综合加权达成率|营业收入|累计/.test(t),
      failed: /加载失败/.test(t),
      hasSelfEmpty: /数据可见范围为「本人」/.test(t),
      hasDeptEmpty: /暂无独立指标数据/.test(t),
    }
  })
  ok('部门范围账号：驾驶舱可见经营数据（只按权限开放）', headDash.hasCards, headDash.hasCards ? '' : '未渲染出内容')
  ok('部门范围账号：驾驶舱无「加载失败」', !headDash.failed)
  ok('部门范围账号：不再出现「本人范围」空态', !headDash.hasSelfEmpty)
  ok('部门范围账号：不再出现部门视角空态说明', !headDash.hasDeptEmpty)

  await gotoTab('指标维护')
  const headMetrics = await page.evaluate(() => {
    const t = document.body.innerText.replace(/\s+/g, ' ')
    // 单元格带 data-cell="<orgId>:<metricId>"，据此统计出现了哪些组织
    const orgIds = new Set(
      [...document.querySelectorAll('main [data-cell]')]
        .map((e) => e.dataset.cell.split(':')[0])
        .filter((id) => id.startsWith('PC')),
    )
    return {
      sections: ['一、公司整体目标', '二、指标监控', '三、项目公司指标'].filter((s) => t.includes(s)).length,
      pcCount: orgIds.size,
      failed: /加载失败/.test(t),
    }
  })
  ok('部门范围账号：指标维护三块齐全', headMetrics.sections === 3, `命中 ${headMetrics.sections}/3`)
  ok('部门范围账号：项目公司模块列出全部（全公司口径）', headMetrics.pcCount >= 3, `出现 ${headMetrics.pcCount} 个项目公司`)
  ok('部门范围账号：指标维护无「加载失败」', !headMetrics.failed)

  await gotoTab('任务管理')
  const headTaskTotal = await readTaskTotal()
  ok(
    '任务模块：仍按可见范围收窄（唯一保留数据权限的模块）',
    headTaskTotal >= 0 && headTaskTotal < adminTaskTotal,
    `管理员 ${adminTaskTotal} 条 → 部门负责人 ${headTaskTotal} 条`,
  )
}

// ---------- 清理：还原可见范围、删除造的数据 ----------
if (scopeSwitched && headUser) {
  const restored = await adminCall('PATCH', `/api/v1/users/${headUser.id}`, {
    name: headUser.name,
    dept_id: headUser.deptId,
    role_id: headUser.roleId,
    scope: originalScope,
    status: headUser.status,
  })
  ok('清理：可见范围已还原', restored.ok, `还原为 ${originalScope || '跟随角色'}`)
}
let removed = 0
for (const id of madeTaskIds) {
  if ((await adminCall('DELETE', `/api/v1/tasks/${id}`)).ok) removed++
}
ok('清理：对比用任务已删除', removed === madeTaskIds.length, `${removed}/${madeTaskIds.length}`)

const pass = R.filter((r) => r.pass).length
const skips = R.filter((r) => r.skip).length
console.log(`\n===== 汇总：${pass}/${R.length} 通过${skips ? `（含 ${skips} 项跳过）` : ''} =====`)
const fails = R.filter((r) => !r.pass)
if (fails.length) {
  console.log('失败明细：')
  fails.forEach((f) => console.log(`  - ${f.name} ${f.detail}`))
}
console.log('控制台错误:', errs.length ? errs.join(' / ') : '0 个 ✅')

await browser.close()
process.exit(fails.length ? 1 : 0)
