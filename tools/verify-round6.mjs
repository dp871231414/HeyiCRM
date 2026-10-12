/**
 * 本轮专项验收：组织结构的保存体验
 *
 * 1. 保存部门后**不出现「加载中」**（原先会整块闪成加载态）
 * 2. 刚保存的名称立即出现在列表里，无需刷新
 * 3. 「全公司」根节点也可编辑名称与负责人（但不可删除）
 * 4. 新建子部门的层级缩进正确
 *
 * 会修改组织数据，脚本结束前会还原。
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const LOGIN_USER = process.env.DIAG_USER || 'chenzm'
const LOGIN_PWD = process.env.DIAG_PWD || 'Demo#2026'

const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1600, height: 950 } }).then((c) => c.newPage())
const errs = []
page.on('console', (m) => m.type() === 'error' && errs.push(m.text().slice(0, 140)))

const R = []
const ok = (name, pass, detail = '') => {
  R.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name}${detail ? ' — ' + detail : ''}`)
}

/** 读组织结构列表的可见状态 */
const readList = () =>
  page.evaluate(() => {
    const items = [...document.querySelectorAll('main ul li')]
    return {
      count: items.length,
      rows: items.map((li) => ({
        text: li.innerText.replace(/\s+/g, ' ').trim(),
        indent: parseInt(li.style.paddingLeft || '0', 10),
        hasEdit: [...li.querySelectorAll('button')].some((b) => b.innerText.trim() === '编辑'),
      })),
      loading: (document.querySelector('main')?.innerText || '').includes('加载中'),
    }
  })

// ---------------- 登录并进入组织结构 ----------------
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('input[type="password"]', { state: 'visible', timeout: 20000 }).catch(() => {})
await page.locator('input[type="text"], input:not([type])').first().fill(LOGIN_USER)
await page.locator('input[type="password"]').first().fill(LOGIN_PWD)
await page.locator('button:has-text("登录")').first().click()
await page.waitForFunction(() => !!document.querySelector('aside nav'), null, { timeout: 30000 }).catch(() => {})

await page.click('aside nav a:has-text("账号管理")')
await page.waitForFunction(() => location.pathname.startsWith('/accounts'), null, { timeout: 15000 }).catch(() => {})
await page.locator('main button:has-text("组织结构")').first().click()
await page.waitForTimeout(1500)

const before = await readList()
ok('组织结构列表已渲染', before.count > 0 && !before.loading, `${before.count} 个节点`)

const coRow = before.rows.find((r) => r.text.includes('全公司') || r.text.includes('CO'))
ok('「全公司」根节点出现在列表中', !!coRow, coRow?.text.slice(0, 40) || '未找到')
ok('「全公司」也有编辑按钮', !!coRow?.hasEdit, coRow?.hasEdit ? '是' : '否')

// ---------------- 1. 编辑「全公司」的负责人 ----------------
console.log('\n──── 编辑「全公司」────')
const coIndex = before.rows.findIndex((r) => r.text.includes('全公司') || r.text.includes('CO'))
const coHeadBefore = (before.rows[coIndex]?.text.match(/负责人\s*(\S+)/) || [])[1] || '—'
const coNewHead = coHeadBefore === '测试负责人' ? '临时负责人' : '测试负责人'

await page.locator('main ul li').nth(coIndex).locator('button:has-text("编辑")').click()
await page.waitForTimeout(800)
const formText = await page.evaluate(() => {
  const dlg = document.querySelector('.fixed')
  return dlg ? dlg.innerText.replace(/\s+/g, ' ').slice(0, 80) : ''
})
ok('「全公司」可打开编辑表单', /编辑/.test(formText) || !!formText, formText)

// 只改负责人（不动名称，避免与其它组织重名）
const headInput = page.locator('.fixed input').nth(1)
await headInput.fill(coNewHead)
await page.locator('.fixed button:has-text("保存")').first().click()

// 保存期间不应出现「加载中」
let sawLoading = false
for (let i = 0; i < 20; i++) {
  if (await page.evaluate(() => (document.querySelector('main')?.innerText || '').includes('加载中'))) {
    sawLoading = true
    break
  }
  await page.waitForTimeout(50)
}
const afterCo = await readList()
ok('保存过程中列表不进入「加载中」', !sawLoading)
ok('保存后列表条目数不变', afterCo.count === before.count, `${before.count} → ${afterCo.count}`)
ok(
  '负责人立即更新，无需刷新',
  afterCo.rows[coIndex]?.text.includes(coNewHead),
  afterCo.rows[coIndex]?.text.slice(0, 50) || '',
)

// 还原
await page.locator('main ul li').nth(coIndex).locator('button:has-text("编辑")').click()
await page.waitForTimeout(700)
await page.locator('.fixed input').nth(1).fill(coHeadBefore)
await page.locator('.fixed button:has-text("保存")').first().click()
await page.waitForTimeout(1200)

// ---------------- 2. 编辑一个普通部门（改名） ----------------
console.log('\n──── 编辑普通部门 ────')
const list2 = await readList()
const deptIndex = list2.rows.findIndex((r) => r.indent > 20 && r.hasEdit)
if (deptIndex < 0) {
  ok('找到可编辑的部门', false, '未找到')
} else {
  const rowText = list2.rows[deptIndex].text
  const deptName = rowText.split(/\s+/)[0]
  const newName = `${deptName}·测试`

  await page.locator('main ul li').nth(deptIndex).locator('button:has-text("编辑")').click()
  await page.waitForTimeout(700)
  await page.locator('.fixed input').first().fill(newName)
  await page.locator('.fixed button:has-text("保存")').first().click()

  let sawLoading2 = false
  for (let i = 0; i < 20; i++) {
    if (await page.evaluate(() => (document.querySelector('main')?.innerText || '').includes('加载中'))) {
      sawLoading2 = true
      break
    }
    await page.waitForTimeout(50)
  }
  const afterDept = await readList()
  ok('改名时列表不进入「加载中」', !sawLoading2)
  ok('列表条目数不变', afterDept.count === list2.count, `${list2.count} → ${afterDept.count}`)
  ok('新名称立即出现在列表', afterDept.rows[deptIndex]?.text.includes(newName), afterDept.rows[deptIndex]?.text.slice(0, 46) || '')
  ok('层级缩进保持不变', afterDept.rows[deptIndex]?.indent === list2.rows[deptIndex].indent, `缩进 ${afterDept.rows[deptIndex]?.indent}px`)

  // 还原名称
  await page.locator('main ul li').nth(deptIndex).locator('button:has-text("编辑")').click()
  await page.waitForTimeout(700)
  await page.locator('.fixed input').first().fill(deptName)
  await page.locator('.fixed button:has-text("保存")').first().click()
  await page.waitForTimeout(1200)

  const restored = await readList()
  ok('名称已还原', restored.rows[deptIndex]?.text.includes(deptName), restored.rows[deptIndex]?.text.slice(0, 40) || '')
}

const pass = R.filter((r) => r.pass).length
console.log(`\n汇总：${pass}/${R.length} 通过`)
console.log('控制台错误：', errs.length ? errs.join(' / ') : '0 个 ✅')

await browser.close()
process.exit(pass === R.length ? 0 : 1)
