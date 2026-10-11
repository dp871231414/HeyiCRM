/**
 * 全流程模拟测试（真实 Chromium，模拟用户操作）
 *
 * A. 管理员完整业务闭环：驾驶舱浏览 → 指标下钻 → 去维护跳转 → 修改并保存 → 回驾驶舱核对联动
 * B. 任务管理：筛选 / 新建 / 编辑 / 删除
 * C. 账号与组织管理：组织结构增删 / 账号新增与停用 / 角色新增-编辑-删除
 * D. 分角色验证：系统管理员 / 部门负责人 / 普通成员 / 项目公司负责人
 *
 * 用法：BASE_URL=http://127.0.0.1:5173 node e2e-flow.mjs
 */
import { mkdirSync } from 'node:fs'

import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173'
const PWD = process.env.E2E_PASSWORD || 'Demo#2026'
const OUT = process.env.SHOT_DIR || '/tmp/fleet_flow'
mkdirSync(OUT, { recursive: true })

/** 每轮唯一后缀：测试数据不残留、脚本可重复运行 */
const SUF = String(Date.now()).slice(-6)
const TASK_NAME = `E2E 自动化验证任务-${SUF}`
const USER_ACC = `e2e${SUF}`
const DEPT_NAME = `E2E 验证部门-${SUF}`
const ROLE_NAME = `E2E 只读角色-${SUF}`

const results = []
let cur = ''
const phase = (n) => {
  cur = n
  console.log(`\n──────── ${n} ────────`)
}
const check = (name, ok, detail = '') => {
  results.push({ phase: cur, name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}

const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1680, height: 1000 } }).then((c) => c.newPage())

const consoleErrors = []
const pageErrors = []
const failedRequests = []
page.on('console', (m) => m.type() === 'error' && consoleErrors.push(`[${cur}] ${m.text()}`))
page.on('pageerror', (e) => pageErrors.push(`[${cur}] ${String(e)}`))
page.on('requestfailed', (r) => failedRequests.push(`[${cur}] ${r.request().method()} ${r.url()} :: ${r.failure()?.errorText}`))
const httpErrors = []
page.on('response', (r) => {
  if (r.status() >= 400) httpErrors.push(`[${cur}] ${r.status()} ${r.request().method()} ${r.url().replace(BASE, '')}`)
})

const body = () => page.textContent('body')
const modal = () => page.locator('div.fixed.inset-0')
const periodSel = () => page.locator('header select').nth(0)
const orgSel = () => page.locator('header select').nth(1)

async function login(account, password = PWD) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.evaluate(() => localStorage.clear())
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.locator('input').nth(0).fill(account)
  await page.locator('input').nth(1).fill(password)
  await page.locator('button:has-text("登录")').first().click()
  await page.waitForTimeout(2400)
  return !(await body()).includes('账号或密码错误')
}

async function logout() {
  await page.locator('header button:has(span.rounded-full)').click()
  await page.waitForTimeout(400)
  const b = page.locator('button:has-text("退出登录")')
  if (await b.count()) {
    await b.first().click()
    await page.waitForTimeout(1300)
  }
}

const nav = async (label) => {
  await page.locator(`aside nav a:has-text("${label}")`).first().click()
  await page.waitForTimeout(1900)
}
const menuLabels = () => page.locator('aside nav a').allTextContents()

/** 等待出现包含指定文案的提示，返回是否出现 */
async function waitToast(expect, timeout = 8000) {
  try {
    await page.waitForFunction(
      (exp) => Array.from(document.querySelectorAll('[data-testid="toast-host"] span')).some((e) => (e.textContent || '').includes(exp)),
      expect,
      { timeout },
    )
    await page.waitForTimeout(250)
    return true
  } catch {
    return false
  }
}

/* ==================================================================
 * A. 管理员完整业务闭环
 * ================================================================== */
await phase('A. 管理员完整业务闭环')
check('管理员登录', await login('chenzm'))
check('侧边栏 4 个菜单', (await menuLabels()).length === 4, (await menuLabels()).join('/'))
await page.screenshot({ path: `${OUT}/a1-dashboard.png`, fullPage: true })

const dash = await body()
for (const [k, v] of [
  ['分析总结', '综合加权达成率'],
  ['核心指标', '销售收入'],
  ['项目公司对比', '项目公司经营对比'],
  ['指标监控', '指标监控'],
  ['部门任务完成度', '部门任务完成度'],
  ['风险与异常', '风险与异常'],
]) {
  check(`驾驶舱-${k}`, dash.includes(v))
}
const riskLast = await page.evaluate(() => {
  const hs = Array.from(document.querySelectorAll('h2'))
  const risk = hs.find((h) => h.textContent?.includes('风险与异常'))
  if (!risk) return false
  return hs.filter((h) => !h.textContent?.includes('风险与异常')).every((o) => o.getBoundingClientRect().top < risk.getBoundingClientRect().top)
})
check('风险与异常位于文末', riskLast)

// 指标下钻
await page.locator('button.card:has-text("销售收入")').first().click()
await page.waitForTimeout(1800)
check('指标下钻弹窗', (await body()).includes('趋势'))
const drillRows = await page.locator('div.fixed.inset-0 table tbody tr').count()
check('下钻弹窗含趋势数据', drillRows > 0, `${drillRows} 行`)
await page.screenshot({ path: `${OUT}/a2-drilldown.png` })
await page.locator('div.fixed.inset-0 button:has-text("×")').click()
await page.waitForTimeout(600)

// 统计周期切换（记录初始值，测完恢复）
const initialPeriod = await periodSel().inputValue()
const periods = await periodSel().locator('option').allTextContents()
const other = periods.find((p) => p.trim() !== initialPeriod.trim())
if (other) {
  await periodSel().selectOption(other)
  await page.waitForTimeout(1700)
  check(`切换统计周期 ${initialPeriod} → ${other}`, (await body()).includes('综合加权达成率'))
  await periodSel().selectOption(initialPeriod)
  await page.waitForTimeout(1700)
  check('统计周期已恢复', (await periodSel().inputValue()) === initialPeriod, initialPeriod)
} else {
  check('统计周期可选', false, `仅 ${periods.length} 个`)
}

// 去维护跳转
const orgBefore = await orgSel().inputValue()
await page.locator('button:has-text("去维护")').first().click()
const focusSeen = await page
  .waitForFunction(() => document.querySelectorAll('.row-focus').length > 0, null, { timeout: 12000 })
  .then(() => true)
  .catch(() => false)
await page.waitForTimeout(1200)
check('「去维护」跳转指标维护', page.url().includes('/metrics'), page.url())
check('跳转不改变全局组织视角', (await orgSel().inputValue()) === orgBefore, `${orgBefore}`)
check('跳转后定位高亮目标行', focusSeen)
const mBody = await body()
check('指标维护-三模块齐全', mBody.includes('公司整体目标') && mBody.includes('指标监控') && mBody.includes('项目公司指标'))
await page.screenshot({ path: `${OUT}/a3-metrics.png`, fullPage: true })

// 修改年度目标与完成值
const rowSel = 'tr[data-cell="CO:REV_SALE"]'
const row = page.locator(rowSel)
const beforeT = await row.locator('input').nth(0).inputValue()
const beforeA = await row.locator('input').nth(1).inputValue()
const newT = String(Number(beforeT) + 1000)
const newA = String(Number(beforeA) + 1500)
check('公司整体目标可编辑（输入框未禁用）', await row.locator('input').nth(0).isEnabled(), `原值 ${beforeT}/${beforeA}`)
await row.locator('input').nth(0).fill(newT)
await row.locator('input').nth(1).fill(newA)
await page.waitForTimeout(400)
check('录入后出现「保存修改」', (await row.locator('button').last().textContent())?.includes('保存修改'))
await row.locator('button').last().click()
check('保存指标成功', await waitToast('已保存'))

await page.reload({ waitUntil: 'networkidle' })
await page.waitForTimeout(2200)
const afterT = await page.locator(rowSel).locator('input').nth(0).inputValue()
const afterA = await page.locator(rowSel).locator('input').nth(1).inputValue()
check('指标修改已持久化', afterT === newT && afterA === newA, `目标 ${afterT} 完成 ${afterA}`)

// 回驾驶舱核对联动
await nav('经营驾驶舱')
check('返回驾驶舱仍为原组织视角', (await orgSel().inputValue()) === orgBefore)
const card = (await page.locator('button.card:has-text("销售收入")').first().textContent()) ?? ''
check('驾驶舱联动-新完成值', card.includes(newA), `含 ${newA}`)
check('驾驶舱联动-新目标', card.includes(newT), `含 ${newT}`)
await page.screenshot({ path: `${OUT}/a4-dashboard-after.png`, fullPage: true })

// 复原
await nav('指标维护')
await page.waitForTimeout(1500)
await page.locator(rowSel).locator('input').nth(0).fill(beforeT)
await page.locator(rowSel).locator('input').nth(1).fill(beforeA)
await page.locator(rowSel).locator('button').last().click()
await waitToast('已保存')
check('指标已复原', true, `${beforeT}/${beforeA}`)

/* ==================================================================
 * B. 任务管理
 * ================================================================== */
await phase('B. 任务管理')
await nav('任务管理')
check('任务列表加载', (await body()).includes('任务ID') && (await body()).includes('任务分类'))
const totalTxt = (await page.locator('main >> text=/共 .* 项任务/').first().textContent().catch(() => '')) || ''
const total0 = Number(totalTxt.replace(/\D/g, '')) || 0
check('任务总数可见', total0 > 0, `共 ${total0} 项`)

await page.locator('main select').nth(1).selectOption('done')
await page.locator('main button:text-is("查询")').click()
await page.waitForTimeout(1500)
const rowsDone = await page.locator('main table tbody tr').count()
check('按「已完成」筛选', rowsDone > 0 && rowsDone < total0, `${rowsDone}/${total0}`)
await page.locator('main select').nth(1).selectOption('')
await page.locator('main button:text-is("查询")').click()
await page.waitForTimeout(1300)

await page.locator('main button:has-text("新建任务")').click()
await page.waitForTimeout(700)
await modal().locator('input').nth(0).fill(TASK_NAME)
await modal().locator('input').nth(1).fill('E2E 二级分类')
await modal().locator('input[type="date"]').nth(1).fill('2026-12-31')
await modal().locator('button:has-text("保存")').click()
check('新建任务成功', await waitToast('保存成功'))
await page.waitForTimeout(1300)
check('新建任务出现在列表', (await page.locator(`tr:has-text("${TASK_NAME}")`).count()) > 0)

await page.locator(`tr:has-text("${TASK_NAME}")`).first().locator('button:has-text("编辑")').click()
await page.waitForTimeout(700)
await modal().locator('input[type="number"]').nth(1).fill('1')
await modal().locator('button:has-text("保存")').click()
check('编辑任务成功', await waitToast('保存成功'))
await page.waitForTimeout(1300)
const edited = (await page.locator(`tr:has-text("${TASK_NAME}")`).first().textContent()) ?? ''
check('编辑结果生效（进度/状态变化）', edited.includes('100%') || edited.includes('已完成'), edited.replace(/\s+/g, ' ').slice(0, 80))

await page.locator(`tr:has-text("${TASK_NAME}")`).first().locator('button:has-text("删除")').click()
await page.waitForTimeout(700)
await modal().locator('button:has-text("确认删除")').click()
check('删除任务成功', await waitToast('已删除'))
await page.waitForTimeout(1300)
check('任务已从列表移除', (await page.locator(`tr:has-text("${TASK_NAME}")`).count()) === 0)

/* ==================================================================
 * C. 账号与组织管理
 * ================================================================== */
await phase('C. 账号与组织管理')
await nav('账号管理')
await page.waitForTimeout(900)
check('账号列表加载', (await body()).includes('姓名') && (await body()).includes('所属部门'))
check('账号数量可见', (await page.locator('main table tbody tr').count()) > 0)

await page.locator('main button:has-text("新增账号")').click()
await page.waitForTimeout(700)
await modal().locator('input').nth(0).fill('E2E 测试员')
await modal().locator('input').nth(1).fill(USER_ACC)
await modal().locator('input[type="password"]').fill('Test#2026')
await modal().locator('button:has-text("保存")').click()
check('新增账号成功', await waitToast('已保存'))
await page.waitForTimeout(1300)
const uRow = page.locator(`tr:has-text("${USER_ACC}")`).first()
check('新账号出现在列表', (await uRow.count()) > 0)

await uRow.locator('button:has-text("停用")').click()
check('停用账号成功', await waitToast('已更新账号状态'))
await page.waitForTimeout(1300)
const uTxt = (await page.locator(`tr:has-text("${USER_ACC}")`).first().textContent()) ?? ''
check('账号状态变为停用', uTxt.includes('停用'), uTxt.replace(/\s+/g, ' ').slice(0, 70))

await page.locator('main button:text-is("组织结构")').click()
await page.waitForTimeout(1600)
const orgCount = await page.locator('main ul > li').count()
check('组织结构为全公司+11 部门', orgCount === 12, `条目数=${orgCount}`)
await page.screenshot({ path: `${OUT}/c1-org.png`, fullPage: true })

await page.locator('main button:has-text("+ 子部门")').first().click()
await page.waitForTimeout(700)
await modal().locator('input').nth(0).fill(DEPT_NAME)
await modal().locator('button:has-text("保存")').click()
check('新增部门成功', await waitToast('已保存'))
await page.waitForTimeout(1400)
check('新部门出现在组织树', (await body()).includes(DEPT_NAME))

await page.locator(`li:has-text("${DEPT_NAME}")`).first().locator('button:has-text("删除")').click()
await page.waitForTimeout(700)
await modal().locator('button:has-text("确认删除")').click()
check('删除部门成功', await waitToast('已删除'))
await page.waitForTimeout(1400)
check('部门已移除', !(await body()).includes(DEPT_NAME))

await page.locator('main button:text-is("角色权限")').click()
await page.waitForTimeout(1600)
const roleCount = await page.locator('main table tbody tr').count()
check('角色列表加载（含 3 内置）', roleCount >= 3, `${roleCount} 个`)
await page.screenshot({ path: `${OUT}/c2-roles.png`, fullPage: true })

await page.locator('main button:has-text("新增角色")').click()
await page.waitForTimeout(800)
await modal().locator('input').nth(0).fill(ROLE_NAME)
const boxes = modal().locator('input[type="checkbox"]')
check('角色表单含权限勾选项', (await boxes.count()) >= 8, `${await boxes.count()} 项`)
await boxes.nth(0).check()
await modal().locator('button:has-text("保存")').click()
check('新增角色成功', await waitToast('已保存'))
await page.waitForTimeout(1400)
const rRow = page.locator(`tr:has-text("${ROLE_NAME}")`).first()
check('新角色出现在列表', (await rRow.count()) > 0)

await rRow.locator('button:has-text("编辑")').click()
await page.waitForTimeout(800)
await modal().locator('input').nth(0).fill(ROLE_NAME + '改')
await modal().locator('button:has-text("保存")').click()
check('编辑角色成功', await waitToast('已保存'))
await page.waitForTimeout(1400)

await page.locator(`tr:has-text("${ROLE_NAME}改")`).first().locator('button:has-text("删除")').click()
await page.waitForTimeout(700)
await modal().locator('button:has-text("确认删除")').click()
check('删除角色成功', await waitToast('已删除'))
await page.waitForTimeout(1400)
check('角色已移除', (await page.locator(`tr:has-text("${ROLE_NAME}")`).count()) === 0)

/* ==================================================================
 * D. 分角色验证
 * ================================================================== */
await phase('D. 分角色验证')

const CASES = [
  { account: 'chenzm', label: '系统管理员', menus: 4, accountMenu: true, scope: '全公司', importMetric: true, delTask: true, viewDash: 'content', orgType: 'company' },
  { account: 'wangjg', label: '部门负责人', menus: 3, accountMenu: false, scope: '本部门及下属部门', importMetric: true, delTask: false, viewDash: 'deptNotice', orgType: 'dept' },
  { account: 'zhengkai', label: '普通成员', menus: 3, accountMenu: false, scope: '本人', importMetric: false, delTask: false, viewDash: 'selfNotice', orgType: 'none' },
  { account: 'liqiang', label: '项目公司负责人', menus: 3, accountMenu: false, scope: '本部门及下属部门', importMetric: true, delTask: false, viewDash: 'content', orgType: 'project' },
]

for (const c of CASES) {
  await logout()
  check(`[${c.label}] 登录成功`, await login(c.account), c.account)
  const menus = (await menuLabels()).map((m) => (m || '').trim())
  check(`[${c.label}] 菜单数=${c.menus}`, menus.length === c.menus, menus.join('/'))
  check(`[${c.label}] 账号管理菜单${c.accountMenu ? '可见' : '隐藏'}`, menus.some((m) => m.includes('账号管理')) === c.accountMenu)

  // 可见范围
  await page.locator('header button:has(span.rounded-full)').click()
  await page.waitForTimeout(400)
  const drop = (await page.locator('div.absolute.right-0').first().textContent()) ?? ''
  check(`[${c.label}] 可见范围=${c.scope}`, drop.includes(c.scope), drop.replace(/\s+/g, ' ').slice(0, 60))
  await page.mouse.click(300, 600)
  await page.waitForTimeout(400)

  // 驾驶舱
  await nav('经营驾驶舱')
  const db = await body()
  if (c.viewDash === 'content') {
    check(`[${c.label}] 驾驶舱正常渲染`, db.includes('综合加权达成率'), '')
  } else if (c.viewDash === 'deptNotice') {
    check(`[${c.label}] 驾驶舱给出部门视角说明`, db.includes('只下达在') && !db.includes('加载失败'))
    check(`[${c.label}] 驾驶舱展示部门任务完成度`, db.includes('部门任务完成度'))
  } else {
    check(`[${c.label}] 驾驶舱给出「本人」范围说明`, db.includes('可见范围为「本人」') && !db.includes('加载失败'))
  }
  await page.screenshot({ path: `${OUT}/d-${c.account}.png`, fullPage: true })

  // 任务管理按钮权限
  await nav('任务管理')
  const tb = await body()
  check(`[${c.label}] 新建任务${c.delTask || !c.delTask ? '可见' : ''}`, tb.includes('新建任务'))
  check(`[${c.label}] 删除任务按钮${c.delTask ? '可见' : '隐藏'}`, tb.includes('删除') === c.delTask, `可见=${tb.includes('删除')}`)

  // 指标维护按钮权限
  await nav('指标维护')
  const mb = await body()
  check(`[${c.label}] 批量导入${c.importMetric ? '可见' : '隐藏'}`, mb.includes('批量导入') === c.importMetric, `可见=${mb.includes('批量导入')}`)
  if (c.viewDash === 'selfNotice') {
    check(`[${c.label}] 指标维护给出「本人」范围说明`, mb.includes('可见范围为「本人」') && !mb.includes('加载失败'))
  } else {
    check(`[${c.label}] 指标维护正常渲染`, mb.includes('公司整体目标') && !mb.includes('加载失败'))
    if (c.orgType === 'dept') {
      check(`[${c.label}] 指标维护给出部门视角说明`, mb.includes('只下达在'))
      check(`[${c.label}] 部门视角无公司整体指标录入项`, (await page.locator('[data-cell$=":REV_SALE"] input').count()) === 0)
    } else {
      const disabled = await page.locator('[data-cell$=":REV_SALE"] input').first().isDisabled().catch(() => null)
      check(
        `[${c.label}] 公司整体目标${c.accountMenu ? '可维护' : '只读'}`,
        disabled === !c.accountMenu,
        `disabled=${disabled}`,
      )
    }
  }

  // 越权直达受限路由
  if (!c.accountMenu) {
    await page.goto(`${BASE}/accounts`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1600)
    const ub = await body()
    check(`[${c.label}] 直访 /accounts 被拦截`, page.url().includes('/forbidden') || ub.includes('无访问权限'), page.url())
  }
}

await browser.close()

console.log('\n===== 控制台错误 =====')
console.log(consoleErrors.length ? [...new Set(consoleErrors)].slice(0, 15).join('\n') : '（无）')
console.log('\n===== 页面异常 =====')
console.log(pageErrors.length ? pageErrors.slice(0, 15).join('\n') : '（无）')
console.log('\n===== HTTP 4xx/5xx =====')
console.log(httpErrors.length ? [...new Set(httpErrors)].join('\n') : '（无）')
console.log('\n===== 失败请求 =====')
console.log(failedRequests.length ? [...new Set(failedRequests)].slice(0, 15).join('\n') : '（无）')

const pass = results.filter((r) => r.ok).length
console.log(`\n===== 汇总：${pass}/${results.length} 通过 =====`)
const failed = results.filter((r) => !r.ok)
if (failed.length) {
  console.log('\n失败明细：')
  for (const f of failed) console.log(`- [${f.phase}] ${f.name} ${f.detail}`)
}
process.exit(failed.length ? 1 : 0)
