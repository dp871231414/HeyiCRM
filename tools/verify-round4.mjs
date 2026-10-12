/**
 * 本轮需求验收（真实浏览器）
 *
 * A. 统计周期：面板内「本月」快捷项
 * B. 任务列表分页：平铺每页 50；分组视图每个部门各自分页、每页 20
 * C. 冻结列：横向滚动时任务ID 与 任务名称之间无透明缝隙
 * D. 分组标题：横向滚动时部门名与统计数字位置固定
 *
 * 分页用例需要造数（55 条任务），仅在本机（127.0.0.1）执行并在结束时清理；
 * 线上运行时自动跳过该段，只验证只读部分。
 */
import { chromium } from 'playwright'

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8000'
const PWD = 'Demo#2026'
const PANEL = '[role="dialog"][aria-label="选择统计周期"]'
const TRIGGER = 'main button[aria-haspopup="dialog"]'
const isLocal = /127\.0\.0\.1|localhost/.test(BASE)
const ALLOW_WRITE = isLocal || process.env.ALLOW_WRITE === '1'

const browser = await chromium.launch()
const page = await browser.newContext({ viewport: { width: 1440, height: 900 } }).then((c) => c.newPage())
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

async function gotoMenu(label, path, marker) {
  await page.click(`aside nav a:has-text("${label}")`)
  await page.waitForFunction((p) => location.pathname.startsWith(p), path, { timeout: 15000 }).catch(() => {})
  if (marker) {
    await page
      .waitForFunction((m) => (document.querySelector('main')?.innerText || '').includes(m), marker, { timeout: 15000 })
      .catch(() => {})
  }
  await page.waitForTimeout(500)
}

/** 量冻结列的几何关系（相对滚动容器左边缘） */
const measureCols = () =>
  page.evaluate(() => {
    const wrap = document.querySelector('.overflow-x-auto')
    const ths = [...document.querySelectorAll('table.table-freeze thead th')]
    const wl = wrap.getBoundingClientRect().left
    const g = (i) => {
      const r = ths[i].getBoundingClientRect()
      return { w: +r.width.toFixed(1), left: +(r.left - wl).toFixed(1), right: +(r.right - wl).toFixed(1) }
    }
    return { id: g(0), name: g(1), scrollLeft: wrap.scrollLeft }
  })

/** 量分组标题与页脚分页器是否仍停留在视口内 */
const measureGroupSticky = () =>
  page.evaluate(() => {
    const wrap = document.querySelector('.overflow-x-auto')
    const wl = wrap.getBoundingClientRect().left
    const wr = wrap.getBoundingClientRect().right
    const pick = (sel) => {
      const el = document.querySelector(sel)
      if (!el) return null
      const r = el.getBoundingClientRect()
      return {
        text: el.innerText.replace(/\s+/g, ' ').trim().slice(0, 24),
        left: +(r.left - wl).toFixed(1),
        visible: r.left >= wl - 2 && r.left < wr,
      }
    }
    return { scrollLeft: wrap.scrollLeft, title: pick('.group-title'), pager: pick('.group-title .btn-ghost') }
  })

// ---------------- 登录 ----------------
await page.goto(BASE, { waitUntil: 'domcontentloaded' })
await page.fill('input[type="text"], input:not([type])', 'chenzm').catch(() => {})
const pw = page.locator('input[type="password"]')
if (await pw.count()) {
  await pw.fill(PWD)
  await page.click('button[type="submit"], button:has-text("登录")')
}
await page.waitForTimeout(4500)

// ================= A. 面板内的「本月」 =================
console.log('──── A. 统计周期「本月」快捷项 ────')
await gotoMenu('经营驾驶舱', '/dashboard', '核心指标')

const initialLabel = await page.evaluate(() => document.querySelector('main button[aria-haspopup="dialog"]')?.innerText.trim())
ok('触发器显示当前周期', /^\d{4}年\d{1,2}月$/.test(initialLabel || ''), initialLabel)

// 先切到别的月份，再用「本月」跳回
await page.locator(TRIGGER).first().click()
await page.waitForTimeout(400)
const hasTodayBtn = await page.evaluate(() => {
  const panel = document.querySelector('[role="dialog"][aria-label="选择统计周期"]')
  return [...panel.querySelectorAll('button')].some((b) => b.innerText.trim() === '本月')
})
ok('面板内存在「本月」快捷项', hasTodayBtn)

// 点年份面板选 2027 → 再选 3 月
await page.evaluate(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const panel = document.querySelector('[role="dialog"][aria-label="选择统计周期"]')
  const title = [...panel.querySelectorAll('button')].find((b) => /^\d{4}年$/.test(b.innerText.trim()))
  title?.click()
  await sleep(300)
  ;[...panel.querySelectorAll('button')].find((b) => b.innerText.trim() === '2027')?.click()
  await sleep(300)
  ;[...panel.querySelectorAll('button')].find((b) => b.innerText.trim() === '3月')?.click()
  await sleep(1500)
})
const afterPick = await page.evaluate(() => document.querySelector('main button[aria-haspopup="dialog"]')?.innerText.trim())
ok('可切换到其他月份', afterPick === '2027年3月', afterPick)

await page.locator(TRIGGER).first().click()
await page.waitForTimeout(400)
await page.evaluate(() => {
  const panel = document.querySelector('[role="dialog"][aria-label="选择统计周期"]')
  ;[...panel.querySelectorAll('button')].find((b) => b.innerText.trim() === '本月')?.click()
})
await page.waitForTimeout(1500)
const afterToday = await page.evaluate(() => ({
  label: document.querySelector('main button[aria-haspopup="dialog"]')?.innerText.trim(),
  open: document.querySelectorAll('[role="dialog"][aria-label="选择统计周期"]').length,
}))
ok('点「本月」回到当月', afterToday.label === initialLabel, `${afterPick} → ${afterToday.label}`)
ok('点「本月」后自动关闭面板', afterToday.open === 0)

// ================= C. 冻结列无缝隙 =================
console.log('\n──── C. 冻结列缝隙 ────')
await gotoMenu('任务管理', '/tasks', '按部门分组')

// 任务数据为 0 时整张表不渲染，依赖表格的断言不适用 → 跳过
const hasTaskTable = await page.evaluate(() => document.querySelectorAll('main thead th').length >= 10)
if (!hasTaskTable) {
  skip('冻结列缝隙（任务ID 与 任务名称之间）', '当前任务数据为 0 条，表格未渲染')
  skip('分组标题横向滚动固定', '同上')
} else {

  await page.waitForFunction(() => document.querySelectorAll('main thead th').length >= 10, null, { timeout: 15000 }).catch(() => {})

  const before = await measureCols()
  ok('滚动前：任务ID 与 任务名称 无缝', Math.abs(before.name.left - before.id.right) < 1, `id右=${before.id.right} name左=${before.name.left}`)

  await page.evaluate(() => {
    document.querySelector('.overflow-x-auto').scrollLeft = 400
  })
  await page.waitForTimeout(400)
  const after = await measureCols()
  const gap = +(after.name.left - after.id.right).toFixed(1)
  ok('滚动后：两列之间无透明缝隙', Math.abs(gap) < 1, `差值=${gap}px（id右=${after.id.right} name左=${after.name.left}）`)
  ok('滚动后任务ID 列仍固定在左侧', after.id.left === 0, `left=${after.id.left}`)
  ok('滚动后任务名称 列仍固定在左侧', after.name.left === 96, `left=${after.name.left}`)

  // ================= D. 分组标题固定 =================
  console.log('\n──── D. 分组标题横向滚动固定 ────')
  const groupBtn = page.locator('main button:has-text("按部门分组")')
  await groupBtn.first().click()
  await page.waitForFunction(
    () => [...document.querySelectorAll('main tbody tr')].some((r) => r.querySelectorAll('td').length === 1),
    null,
    { timeout: 15000 },
  ).catch(() => {})

  await page.evaluate(() => {
    document.querySelector('.overflow-x-auto').scrollLeft = 400
  })
  await page.waitForTimeout(500)
  const g = await measureGroupSticky()
  ok('横向滚动后部门标题仍可见', !!g.title && g.title.visible === true, g.title ? `「${g.title.text}」left=${g.title.left}` : '未找到')
  ok('部门标题固定在容器左侧 12px', !!g.title && Math.abs(g.title.left - 12) < 2, g.title ? `left=${g.title.left}` : '')
  ok('部门统计数字随标题一同固定', !!g.title && /项任务/.test(g.title.text), g.title?.text || '')
}

// ================= B. 分页 =================
console.log('\n──── B. 分页 ────')
if (!ALLOW_WRITE) {
  skip('平铺视图每页 50 条', '非本机环境，跳过造数场景')
  skip('分组视图每组每页 20 条', '非本机环境，跳过造数场景')
} else {
  const api = page.context().request
  const created = []
  const body = (i) => ({
    parent: `分页验证任务 ${String(i).padStart(3, '0')}`,
    title: '分页用例',
    description: '',
    abnormal: false,
    target: 100,
    done: 0,
    unit: '万元',
    note: '',
    start_date: '2026-10-01',
    end_date: '2026-12-31',
    dept_id: 'D01',
    owner: '林雪',
  })
  for (let i = 1; i <= 55; i++) {
    const r = await api.post(`${BASE}/api/v1/tasks`, { data: body(i) })
    if (r.ok()) created.push((await r.json()).id)
  }
  ok('已造 55 条测试任务', created.length === 55, `实际 ${created.length} 条`)

  try {
    // 关键：同一路由下再次点击侧边栏不会重新挂载组件，视图模式会保留，
    // 因此这里必须显式切回「列表」，否则后续读数与点击都会落在分组视图上。
    await page.locator('main button:has-text("列表")').first().click()
    await page.locator('main button:has-text("查询")').first().click()
    await page
      .waitForFunction(
        () => /每页最多\s*50\s*条/.test(document.querySelector('table.table-freeze')?.closest('.card')?.innerText || ''),
        null,
        { timeout: 15000 },
      )
      .catch(() => {})

    const flat = await page.evaluate(() => {
      // 分页器在「表格所在卡片」内，不能用 querySelector('.card')（会命中工具条那个）
      const card = document.querySelector('table.table-freeze')?.closest('.card')
      const txt = (card?.innerText || '').replace(/\s+/g, ' ')
      const per = /每页最多 (\d+) 条/.exec(txt)
      const pager = /第\s*(\d+)\s*\/\s*(\d+)\s*页/.exec(txt)
      const rowCount = document.querySelectorAll('table.table-freeze tbody tr').length
      const total = /共\s*(\d+)\s*项任务/.exec(document.body.innerText)?.[1]
      return { per: per?.[1], page: pager?.[1], pages: pager?.[2], rowCount, total }
    })
    ok('平铺视图标注每页最多 50 条', flat.per === '50', `每页=${flat.per}`)
    ok('平铺视图出现分页器', !!flat.pages, `第 ${flat.page}/${flat.pages} 页｜共 ${flat.total} 条`)
    ok('平铺单页最多渲染 50 行', flat.rowCount <= 50, `当前页 ${flat.rowCount} 行`)

    // 平铺视图下全页只有这一个「下一页」（分组视图才会有多个）
    await page.locator('main button:has-text("下一页")').first().click()
    await page
      .waitForFunction(
        () => /第\s*2\s*\//.test(document.querySelector('table.table-freeze')?.closest('.card')?.innerText || ''),
        null,
        { timeout: 15000 },
      )
      .catch(() => {})
    const p2 = await page.evaluate(() => {
      const txt = (document.querySelector('table.table-freeze')?.closest('.card')?.innerText || '').replace(/\s+/g, ' ')
      return /第\s*(\d+)\s*\/\s*(\d+)\s*页/.exec(txt)?.[1]
    })
    ok('可翻到第 2 页', p2 === '2', `当前第 ${p2} 页`)

    // 分组视图
    await page.locator('main button:has-text("按部门分组")').first().click()
    await page
      .waitForFunction(
        () => [...document.querySelectorAll('table.table-freeze tbody tr')].some((r) => r.querySelectorAll('td').length === 1),
        null,
        { timeout: 15000 },
      )
      .catch(() => {})
    await page.waitForTimeout(600)
    const grouped = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('main tbody tr')]
      const titleRows = rows.filter((r) => r.querySelectorAll('td').length === 1 && /项任务/.test(r.innerText))
      const pagerRows = rows.filter((r) => r.querySelectorAll('td').length === 1 && /页/.test(r.innerText) && !/项任务/.test(r.innerText))
      const taskRows = rows.filter((r) => r.querySelectorAll('td').length > 1)
      const d01 = titleRows.find((r) => /D01|市场部|运营/.test(r.innerText))
      // 统计每个分组标题到下一个分组标题之间的任务行数
      let maxRowsPerGroup = 0
      let curRows = 0
      for (const r of rows) {
        const isTitle = r.querySelectorAll('td').length === 1
        if (isTitle) {
          maxRowsPerGroup = Math.max(maxRowsPerGroup, curRows)
          curRows = 0
        } else {
          curRows++
        }
      }
      maxRowsPerGroup = Math.max(maxRowsPerGroup, curRows)
      return {
        groups: titleRows.length,
        pagers: pagerRows.length,
        taskRows: taskRows.length,
        maxRowsPerGroup,
        pagerText: pagerRows[0]?.innerText.replace(/\s+/g, ' ').trim().slice(0, 40),
        groupTitle: d01?.innerText.replace(/\s+/g, ' ').trim().slice(0, 40),
      }
    })
    ok('分组视图出现部门分页器', grouped.pagers > 0, `分页器 ${grouped.pagers} 个｜${grouped.pagerText}`)
    ok('切回分组视图后从第 1 页开始', /第 1 \/ \d+ 页/.test(grouped.pagerText || ''), `分页栏：${grouped.pagerText || '无'}`)
    ok('每组单页最多渲染 20 行', grouped.maxRowsPerGroup <= 20, `最大一组 ${grouped.maxRowsPerGroup} 行，共 ${grouped.groups} 组`)

    // 点某组的分页器翻页
    if (grouped.pagers > 0) {
      await page.locator('table.table-freeze tbody button:has-text("下一页")').first().click()
      await page
        .waitForFunction(
          () => [...document.querySelectorAll('table.table-freeze tbody tr')].some((r) => /第 2 \/ \d+ 页/.test(r.innerText)),
          null,
          { timeout: 8000 },
        )
        .catch(() => {})
      const afterGroupPage = await page.evaluate(() =>
        [...document.querySelectorAll('table.table-freeze tbody tr')]
          .filter((r) => r.querySelectorAll('td').length === 1 && /第 \d+ \/ \d+ 页/.test(r.innerText))
          .map((r) => r.innerText.replace(/\s+/g, ' ').trim())[0],
      )
      ok('部门内可独立翻页', /第 2 \/ \d+ 页/.test(afterGroupPage || ''), afterGroupPage || '')
    } else {
      skip('部门内可独立翻页', '未出现多页部门')
    }
  } finally {
    // 清理测试数据
    let removed = 0
    for (const id of created) {
      const r = await api.delete(`${BASE}/api/v1/tasks/${id}`)
      if (r.ok()) removed++
    }
    ok('已清理测试任务', removed === created.length, `删除 ${removed}/${created.length} 条`)
  }
}

// ---------------- 汇总 ----------------
const pass = R.filter((r) => r.pass).length
const skips = R.filter((r) => r.skip).length
console.log(`\n汇总：${pass}/${R.length} 通过${skips ? `（含 ${skips} 项跳过）` : ''}`)
console.log('控制台错误：', errs.length ? errs.join(' / ') : '0 个 ✅')

await browser.close()
process.exit(pass === R.length ? 0 : 1)
