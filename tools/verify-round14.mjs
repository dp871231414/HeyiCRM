/**
 * 第十四轮浏览器验收 · 市场部锁定 + 漏斗按二级部门筛选 + 负责人限定与部门带出 + 项目重生成
 *
 * 用法：BASE_URL=http://127.0.0.1:8000 DIAG_USER=admin DIAG_PWD=123456 node verify-round14.mjs
 *
 * 覆盖：
 *  A. 组织结构中「市场部（D01）」按 ID 锁定不可删除（名称/负责人仍可改），删除接口返回 409；
 *  B. 经营驾驶舱「市场项目概览」提供「全部 / 市场1部 / 市场2部…」筛选标签，随组织变化同步，
 *     选中二级部门后漏斗仅统计该部门负责人项目；
 *  C. 项目管理「负责人」仅可填市场部及下属部门人员，选负责人后「所属部门」自动带出其直接部门；
 *  D. 「重新生成」按当前市场部人员清单删除并重建项目数据，项目数 = 市场部人员数且均带所属部门。
 */
import pw from '/Users/gavin/.workbuddy/binaries/node/workspace/node_modules/playwright-core/index.js'
const { chromium } = pw

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const USER = process.env.DIAG_USER || 'admin'
const PWD = process.env.DIAG_PWD || '123456'

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
page.on('console', (m) => {
  if (m.type() === 'error') errs.push(m.text())
})
page.on('pageerror', (e) => errs.push(String(e)))
const httpErrs = []
page.on('response', (r) => {
  if (r.status() >= 400) httpErrs.push('HTTP ' + r.status() + ' ' + r.url())
})

await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
await page.fill('input[type="text"], input:not([type])', USER)
await page.fill('input[type="password"]', PWD)
await page.click('button[type="submit"]')
await page.waitForURL('**/dashboard', { timeout: 20000 })
await page.waitForTimeout(1500)

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

const bodyHas = (s) => page.evaluate((t) => document.body.innerText.includes(t), s)

// =============================================== 一、市场部锁定不可删除
console.log('\n一、市场部（D01）按 ID 锁定，不可删除')

await page.goto(BASE + '/accounts', { waitUntil: 'networkidle' })
await page.waitForTimeout(800)
await page.click('button:has-text("组织结构")')
await page.waitForTimeout(900)

ok('组织结构列表出现「默认市场部 · 不可删除」标识', await bodyHas('默认市场部 · 不可删除'))
ok('市场部行显示「🔒 锁定」而非删除按钮', await bodyHas('🔒 锁定'))

const delD01 = await api('/api/v1/orgs/D01', { method: 'DELETE' })
ok('删除市场部接口返回 409', delD01.status === 409, 'HTTP ' + delD01.status)
ok('拒绝原因含「市场部」', !!delD01.body && /市场部/.test(JSON.stringify(delD01.body)))

// 二级部门（市场1部 D12）本身不锁定：仅市场部按 ID 锁定，二级部门名称/负责人仍可编辑
const patchD12 = await api('/api/v1/orgs/D12', {
  method: 'PATCH',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: '市场1部', head: '—' }),
})
ok('二级部门（市场1部）仍可编辑名称/负责人', patchD12.status === 200, 'HTTP ' + patchD12.status)

// =============================================== 二、漏斗按二级部门筛选
console.log('\n二、经营驾驶舱 · 市场项目概览按二级部门筛选')

// 先按市场部人员清单重新生成，确保数据确定且负责人均属市场子树
const reseed = await api('/api/v1/market-projects/reseed', { method: 'POST' })
ok('重新生成接口成功', reseed.status === 200, 'created=' + (reseed.body && reseed.body.created))

const owners = await api('/api/v1/meta/market-owners')
const ownerCount = Array.isArray(owners.body) ? owners.body.length : 0
ok('市场部人员清单非空', ownerCount > 0, 'market users=' + ownerCount)

await page.goto(BASE + '/dashboard', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

ok('驾驶舱含「市场项目概览」', await bodyHas('市场项目概览'))
ok('含「按部门筛选」标签', await bodyHas('按部门筛选'))
ok('筛选标签含「全部」', await bodyHas('全部'))
ok('筛选标签含二级部门「市场1部」', await bodyHas('市场1部'))
ok('筛选标签含二级部门「市场2部」', await bodyHas('市场2部'))

// 点击二级部门后，漏斗仅统计该部门负责人项目
await page.click('button:has-text("市场1部")')
await page.waitForTimeout(1200)
ok('选中二级部门后显示「当前：市场1部」', await bodyHas('当前：市场1部'))

const full = await api('/api/v1/dashboard/project-funnel')
const d12 = await api('/api/v1/dashboard/project-funnel?dept=D12')
const fullTotal = full.body.stages.reduce((a, s) => a + s.count, 0)
const d12Total = d12.body.stages.reduce((a, s) => a + s.count, 0)
ok('全部口径项目数 > 单二级部门口径', fullTotal > d12Total && d12Total > 0, `full=${fullTotal} d12=${d12Total}`)
ok(
  '部门选项随组织动态返回（D12 / D13）',
  d12.body.deptOptions.some((o) => o.id === 'D12') && d12.body.deptOptions.some((o) => o.id === 'D13'),
)

// 切回全部
await page.click('button:has-text("全部")')
await page.waitForTimeout(800)

// =============================================== 三、负责人限定 + 所属部门自动带出
console.log('\n三、项目管理 · 负责人仅限市场部及下属，选后自动带出所属部门')

await page.goto(BASE + '/market', { waitUntil: 'networkidle' })
await page.waitForTimeout(1000)
await page.click('button:has-text("新建项目")')
await page.waitForTimeout(800)

const ownerSel = page.locator('select').filter({ hasText: '胡启迪' }).first()
const ownerOptions = await ownerSel.evaluate((s) => [...s.options].map((o) => o.textContent.trim()))
ok('负责人下拉包含市场人员 胡启迪（市场1部）', ownerOptions.some((t) => /胡启迪（市场1部）/.test(t)), ownerOptions.join(' | '))
ok('负责人下拉不包含非市场部人员（赵国强·资产部）', !ownerOptions.some((t) => t.includes('赵国强')))

// 选胡启迪 → 所属部门带出 市场1部
await ownerSel.selectOption({ label: ownerOptions.find((t) => /胡启迪（市场1部）/.test(t)) })
await page.waitForTimeout(400)
const dept1 = await page.locator('input[placeholder="选择负责人后自动带出"]').inputValue()
ok('选胡启迪后所属部门自动带出「市场1部」', dept1 === '市场1部', 'dept=' + dept1)

// 改选周春泉 → 所属部门带出 市场2部
const owns = await page.locator('select').filter({ hasText: '周春泉' }).first().evaluate((s) => [...s.options].map((o) => o.textContent.trim()))
await page.locator('select').filter({ hasText: '周春泉' }).first().selectOption({ label: owns.find((t) => /周春泉（市场2部）/.test(t)) })
await page.waitForTimeout(400)
const dept2 = await page.locator('input[placeholder="选择负责人后自动带出"]').inputValue()
ok('改选周春泉后所属部门自动带出「市场2部」', dept2 === '市场2部', 'dept=' + dept2)

// 不落库，关闭表单
await page.keyboard.press('Escape')
await page.waitForTimeout(400)

// =============================================== 四、重新生成项目数据（UI 触发）
console.log('\n四、按市场部人员清单重新生成项目数据')

await page.click('button:has-text("重新生成")')
await page.waitForTimeout(600)
ok('弹出「重新生成项目数据」对话框', await bodyHas('重新生成项目数据'))
await page.click('button:has-text("确认重新生成")')
await page.waitForTimeout(1200)

const after = await api('/api/v1/market-projects?size=500')
const total = after.body.total
const items = after.body.items || []
const allHaveDept = items.every((it) => it.ownerDeptId)
const ownersInList = new Set(owners.body.map((o) => o.name))
const ownersAllValid = items.every((it) => ownersInList.has(it.owner))
ok('重新生成后项目数 = 市场部人员数', total === ownerCount, `total=${total} owners=${ownerCount}`)
ok('每个项目都带负责人所属部门', allHaveDept)
ok('负责人均来自市场部人员清单', ownersAllValid)

// =============================================== 汇总
// 控制台里那条 409 是第一部分「删除市场部接口应返回 409」刻意触发的，属预期，不计入异常
const realErrs = errs.filter((e) => !/409|Conflict/.test(e))
const realHttp = httpErrs.filter((e) => !/HTTP (409|422) /.test(e))
console.log('\n控制台错误：' + realErrs.length + ' 个' + (realErrs.length ? ' NG' : ' OK'))
if (realErrs.length) realErrs.slice(0, 5).forEach((e) => console.log('   -', e))
console.log('非预期 HTTP 错误：' + realHttp.length + ' 个' + (realHttp.length ? ' NG' : ' OK'))
if (realHttp.length) realHttp.slice(0, 8).forEach((e) => console.log('   -', e))
console.log('\n结果：' + passed + ' 通过，' + failed + ' 失败')

await browser.close()
process.exit(failed ? 1 : 0)
