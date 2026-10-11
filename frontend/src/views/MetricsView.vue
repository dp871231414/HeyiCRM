<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center gap-2.5">
      <p class="text-xs text-slate-500">
        数据截至 <b class="text-slate-700">{{ board?.dataAsOf || '—' }}</b> · 年度时间进度
        <b class="text-slate-700">{{ fmtPct(board?.timeProgress) }}</b> · 目标按年度存储，全年各月度周期共用
      </p>
      <div class="ml-auto flex items-center gap-2">
        <button class="btn-ghost" @click="download(metricApi.templateUrl(), '指标数据导入标准模板.xlsx')">下载模板</button>
        <label v-if="auth.hasPerm('metric.import')" class="btn-ghost cursor-pointer">
          批量导入
          <input type="file" accept=".xlsx" class="hidden" @change="onImport" />
        </label>
        <button class="btn-primary" @click="router.push({ name: 'dashboard' })">查看驾驶舱</button>
      </div>
    </div>

    <div v-if="board && view.orgId !== 'CO'" class="card p-3.5 border-brand-100 bg-brand-50 text-xs text-brand-700">
      当前组织视角为「{{ board.orgId }}」。公司整体目标与监控指标仅具备全公司数据可见范围的管理员可维护；
      项目公司指标按可见范围维护。指标目标只下达在公司与项目公司层级，部门视角无独立指标数据。
    </div>

    <div v-if="error" class="card p-4 border-bad-100 bg-bad-50 text-sm text-bad-600 flex items-center gap-3">
      加载失败：{{ error }} <button class="btn-ghost btn-sm" @click="load">重试</button>
    </div>
    <div v-if="loading" class="card p-10 text-center text-slate-400 text-sm">加载中…</div>

    <!-- 本人范围：无组织维度数据 -->
    <div v-else-if="noOrgDimension" class="card p-8 text-center space-y-2">
      <div class="text-sm font-bold text-slate-700">当前账号的数据可见范围为「本人」</div>
      <p class="text-xs text-slate-500 leading-relaxed">
        指标按组织维度归集，「本人」范围不含任何组织的指标数据，因此本页无内容可维护。<br />
        你仍可在「任务管理」中查看与维护本人负责的任务；如需录入指标，
        请联系管理员将数据可见范围调整为「本部门」或更高。
      </p>
    </div>

    <template v-else-if="board">
      <!-- 模块一 · 公司整体目标 -->
      <section>
        <div class="flex items-center justify-between mb-2.5">
          <h2 class="text-sm font-bold text-slate-900">一、公司整体目标</h2>
          <span class="text-xs text-slate-400">完成值为年初至今累计；运营车辆为期末快照</span>
        </div>
        <div v-if="deptView" class="card p-8 text-center text-xs text-slate-500 leading-relaxed">
          指标目标只下达在<b class="text-slate-700">公司与项目公司</b>层级，{{ board.orgId }} 视角无独立指标数据。
        </div>
        <div v-else class="card overflow-x-auto">
          <table class="w-full min-w-[1080px]">
            <thead>
              <tr class="border-b border-slate-200">
                <th class="th">指标</th>
                <th class="th w-[150px]">年度目标</th>
                <th class="th w-[140px]">完成值</th>
                <th class="th w-[168px]">完成率</th>
                <th class="th w-[130px]">回款</th>
                <th class="th w-[150px]">回款率</th>
                <th class="th w-[110px]">状态</th>
                <th class="th w-[100px] text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in board.annual"
                :key="row.metricId"
                :data-cell="`${board.orgId}:${row.metricId}`"
                class="border-b border-slate-100 last:border-0"
                :class="{ 'row-dirty': isDirty(board.orgId, row.metricId) }"
              >
                <td class="td max-w-[280px]">
                  <div class="font-semibold text-slate-800">{{ row.name }}</div>
                  <div class="text-[11px] text-slate-400 whitespace-normal leading-snug">
                    责任部门 {{ row.ownerOrgName || '—' }} · 权重 {{ row.weight }}
                  </div>
                </td>
                <td class="td">
                  <input
                    v-model="draft[cellKey(board.orgId, row.metricId)].t"
                    class="input !py-1.5 text-right font-mono"
                    :disabled="!canEdit(board.orgId)"
                    inputmode="decimal"
                  />
                </td>
                <td class="td">
                  <input
                    v-model="draft[cellKey(board.orgId, row.metricId)].a"
                    class="input !py-1.5 text-right font-mono"
                    :disabled="!canEdit(board.orgId)"
                    inputmode="decimal"
                  />
                </td>
                <td class="td">
                  <div class="flex items-center gap-2">
                    <span class="font-bold w-14" :class="rateClass(row.light)">{{ row.rateText }}</span>
                    <span class="text-[11px]" :class="(row.vsTime ?? 0) >= 0 ? 'text-good-600' : 'text-bad-600'">
                      vs {{ fmtDelta(row.vsTime) }}
                    </span>
                  </div>
                </td>
                <td class="td">
                  <input
                    v-if="row.hasCollection"
                    v-model="draft[cellKey(board.orgId, row.metricId)].c"
                    class="input !py-1.5 text-right font-mono"
                    :disabled="!canEdit(board.orgId)"
                    inputmode="decimal"
                  />
                  <span v-else class="text-slate-300">—</span>
                </td>
                <td class="td">
                  <StatusBadge v-if="row.hasCollection" :light="row.collLight" :text="fmtPct(row.collRate)" />
                  <span v-else class="text-slate-300">—</span>
                </td>
                <td class="td"><StatusBadge :light="row.light" /></td>
                <td class="td text-right">
                  <button
                    class="btn-sm"
                    :class="isDirty(board.orgId, row.metricId) ? 'btn-primary' : 'btn-ghost'"
                    :disabled="!canEdit(board.orgId) || saving === cellKey(board.orgId, row.metricId) || !isDirty(board.orgId, row.metricId)"
                    @click="saveRow(row, board.orgId)"
                  >
                    {{ saving === cellKey(board.orgId, row.metricId) ? '保存中…' : isDirty(board.orgId, row.metricId) ? '保存修改' : '已保存' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 模块二 · 指标监控 -->
      <section v-if="board.monitor.length && !deptView">
        <div class="flex items-center justify-between mb-2.5">
          <h2 class="text-sm font-bold text-slate-900">二、指标监控</h2>
          <span class="text-xs text-slate-400">无目标值、不判红黄绿灯，按当期快照录入</span>
        </div>
        <div class="card p-4 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
          <div
            v-for="row in board.monitor"
            :key="row.metricId"
            class="rounded-lg border border-slate-200 px-3.5 py-3"
            :class="{ 'row-dirty': isDirty(board.orgId, row.metricId) }"
          >
            <div class="text-xs text-slate-500">{{ row.name }}</div>
            <input
              v-model="draft[cellKey(board.orgId, row.metricId)].a"
              class="input !py-1.5 mt-1.5 text-lg font-bold font-mono"
              :disabled="!canEdit(board.orgId)"
              inputmode="decimal"
            />
            <div class="mt-2 flex items-center justify-between">
              <span class="text-[11px] text-slate-400">{{ row.unit }} · 上期 {{ fmt(prevMap[row.metricId]) }}</span>
              <button
                class="btn-sm"
                :class="isDirty(board.orgId, row.metricId) ? 'btn-primary' : 'btn-ghost'"
                :disabled="!canEdit(board.orgId) || !isDirty(board.orgId, row.metricId)"
                @click="saveRow(row, board.orgId)"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 模块三 · 项目公司指标 -->
      <section>
        <div class="flex items-center justify-between mb-2.5">
          <h2 class="text-sm font-bold text-slate-900">三、项目公司指标</h2>
          <button v-if="canAddProject" class="btn-primary btn-sm" @click="openProjectForm()">+ 新增项目公司</button>
        </div>

        <div v-if="!board.project.companies.length" class="card p-8 text-center text-sm text-slate-400">
          可见范围内暂无项目公司
        </div>

        <div v-else class="card overflow-x-auto">
          <table class="w-full min-w-[1120px]">
            <thead>
              <tr class="border-b border-slate-200">
                <th class="th" rowspan="2">项目公司</th>
                <th v-for="m in board.project.metrics" :key="m.id" class="th text-center" :colspan="m.id === 'OP_REV' ? 4 : 3">
                  {{ m.name }}{{ m.snapshot ? '（期末快照）' : '' }}
                </th>
                <th class="th text-center" rowspan="2">完成率</th>
                <th class="th text-center" rowspan="2">操作</th>
              </tr>
              <tr class="border-b border-slate-200">
                <template v-for="m in board.project.metrics" :key="`${m.id}-sub`">
                  <th class="th text-right !bg-slate-50/70">目标</th>
                  <th class="th text-right !bg-slate-50/70">完成</th>
                  <th class="th text-right !bg-slate-50/70">达成</th>
                  <template v-if="m.id === 'OP_REV'">
                    <th class="th text-right !bg-slate-50/70">回款率</th>
                  </template>
                </template>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="c in board.project.companies"
                :key="c.orgId"
                class="border-b border-slate-100 last:border-0"
                :class="hasDirty(c.orgId) ? 'row-dirty' : ''"
              >
                <td class="td">
                  <div class="font-semibold text-slate-800">{{ c.name }}</div>
                  <div class="text-[11px] text-slate-400">负责人 {{ c.head }} · 已录 {{ c.filled }}/{{ c.total }}</div>
                </td>
                <template v-for="m in board.project.metrics" :key="`${c.orgId}-${m.id}`">
                  <td class="td" :data-cell="`${c.orgId}:${m.id}`">
                    <input
                      v-model="draft[cellKey(c.orgId, m.id)].t"
                      class="input !py-1 text-right font-mono !w-[92px]"
                      :disabled="!canEdit(c.orgId)"
                      inputmode="decimal"
                    />
                  </td>
                  <td class="td">
                    <input
                      v-model="draft[cellKey(c.orgId, m.id)].a"
                      class="input !py-1 text-right font-mono !w-[92px]"
                      :disabled="!canEdit(c.orgId)"
                      inputmode="decimal"
                    />
                  </td>
                  <td class="td">
                    <StatusBadge :light="cellOf(c, m.id)?.light ?? 'none'" :text="cellOf(c, m.id)?.rateText" />
                  </td>
                  <template v-if="m.id === 'OP_REV'">
                    <td class="td">
                      <input
                        v-model="draft[cellKey(c.orgId, m.id)].c"
                        class="input !py-1 text-right font-mono !w-[92px]"
                        :disabled="!canEdit(c.orgId)"
                        inputmode="decimal"
                      />
                    </td>
                  </template>
                </template>
                <td class="td text-center">
                  <span
                    class="font-bold"
                    :class="c.completion === null ? 'text-slate-400' : c.completion >= 0.98 ? 'text-good-600' : c.completion >= 0.9 ? 'text-warn-600' : 'text-bad-600'"
                  >
                    {{ fmtPct(c.completion) }}
                  </span>
                </td>
                <td class="td text-center whitespace-nowrap">
                  <button
                    class="btn-sm"
                    :class="hasDirty(c.orgId) ? 'btn-primary' : 'btn-ghost'"
                    :disabled="!canEdit(c.orgId) || saving === c.orgId || !hasDirty(c.orgId)"
                    @click="saveProject(c)"
                  >
                    {{ saving === c.orgId ? '保存中…' : hasDirty(c.orgId) ? '保存' : '已保存' }}
                  </button>
                  <template v-if="canAddProject">
                    <button class="btn-ghost btn-sm ml-1.5" @click="openProjectForm(c)">编辑</button>
                    <button class="btn-danger btn-sm ml-1.5" @click="askDeleteProject(c)">删除</button>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <!-- 项目公司表单 -->
    <ModalDialog :open="projectFormOpen" :title="projectForm.id ? '编辑项目公司' : '新增项目公司'" @close="projectFormOpen = false">
      <div class="space-y-4">
        <div>
          <label class="label">公司名称</label>
          <input v-model.trim="projectForm.name" class="input" placeholder="如：合一重卡运营公司" />
        </div>
        <div>
          <label class="label">负责人</label>
          <input v-model.trim="projectForm.head" class="input" placeholder="负责人姓名" />
        </div>
        <div v-if="!projectForm.id" class="space-y-2">
          <label class="label">年度目标（可留空，后续在列表补录）</label>
          <div v-for="m in board?.project.metrics ?? []" :key="m.id" class="flex items-center gap-2">
            <span class="text-xs text-slate-500 w-28">{{ m.name }}</span>
            <input v-model.number="projectForm.targets[m.id]" type="number" class="input !py-1.5" :placeholder="m.unit" />
          </div>
        </div>
        <p v-if="projectError" class="text-sm text-bad-600">{{ projectError }}</p>
      </div>
      <template #footer>
        <button class="btn-ghost" @click="projectFormOpen = false">取消</button>
        <button class="btn-primary" :disabled="saving === 'project'" @click="saveProjectForm">保存</button>
      </template>
    </ModalDialog>

    <!-- 删除项目公司 -->
    <ModalDialog :open="!!projectDelete" title="确认删除项目公司" width="sm" @close="projectDelete = null">
      <div v-if="projectDelete" class="text-sm text-slate-600 space-y-2">
        <p>将删除「{{ projectDelete.name }}」，并连带清理其指标数据与任务：</p>
        <ul class="list-disc pl-5 text-xs text-slate-500 space-y-1">
          <li>年度目标 {{ projectDelete.impact.targets }} 条</li>
          <li>完成值 {{ projectDelete.impact.actuals }} 条</li>
          <li>关联任务 {{ projectDelete.impact.tasks }} 条</li>
          <li>关联账号 {{ projectDelete.impact.users }} 个（将停用，不删除）</li>
        </ul>
        <p class="text-xs text-bad-600">该操作不可撤销。</p>
      </div>
      <template #footer>
        <button class="btn-ghost" @click="projectDelete = null">取消</button>
        <button class="btn-danger" @click="doDeleteProject">确认删除</button>
      </template>
    </ModalDialog>

    <!-- 导入结果 -->
    <ModalDialog :open="importOpen" title="批量导入结果" width="lg" @close="importOpen = false">
      <div v-if="importResult">
        <p class="text-sm" :class="importResult.imported ? 'text-good-700' : 'text-bad-700'">
          {{ importResult.imported ? `成功导入 ${importResult.imported} 行。` : '存在错误行，本次未写入任何数据。' }}
        </p>
        <div v-if="importResult.errors.length" class="mt-3 max-h-72 overflow-y-auto border border-slate-200 rounded-lg">
          <table class="w-full">
            <thead>
              <tr>
                <th class="th w-20">行号</th>
                <th class="th w-40">字段</th>
                <th class="th">错误说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(e, i) in importResult.errors" :key="i" class="border-b border-slate-100 bg-bad-50/40">
                <td class="td">{{ e.row }}</td>
                <td class="td text-bad-700 font-semibold">{{ e.field }}</td>
                <td class="td whitespace-normal">{{ e.msg }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <template #footer>
        <button class="btn-primary" @click="importOpen = false">知道了</button>
      </template>
    </ModalDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { dashboardApi, downloadFile, metricApi, projectApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useViewStore } from '@/stores/view'
import type { ImportResult, MetricBoard, MetricRow, ProjectCompanyBlock, ProjectItem } from '@/types'
import { fmt, fmtDelta, fmtPct } from '@/utils/format'

const auth = useAuthStore()
const app = useAppStore()
const view = useViewStore()
const router = useRouter()

const board = ref<MetricBoard | null>(null)
const loading = ref(false)
const error = ref('')
const saving = ref('')
const draft = reactive<Record<string, { t: string; a: string; c: string }>>({})
const baseline = reactive<Record<string, { t: string; a: string; c: string }>>({})
const prevMap = reactive<Record<string, number>>({})

const projectFormOpen = ref(false)
const projectForm = reactive<{ id: string; name: string; head: string; targets: Record<string, number | null> }>({
  id: '',
  name: '',
  head: '',
  targets: {},
})
const projectError = ref('')
const projectDelete = ref<ProjectItem | null>(null)
const importOpen = ref(false)
const importResult = ref<ImportResult | null>(null)

const download = downloadFile
const canAddProject = computed(() => !!board.value?.canEditAll)
/** 部门/班组视角：指标目标只下达在公司与项目公司层级，故无独立指标数据 */
const deptView = computed(() => ['dept', 'team'].includes(board.value?.orgType ?? ''))

function cellKey(orgId: string, metricId: string) {
  return `${orgId}|${metricId}`
}
function canEdit(orgId: string) {
  if (!auth.hasPerm('metric.edit')) return false
  // 公司整体目标 / 监控指标：仅具备「全公司」可见范围、且当前为全公司视角时可维护
  if (orgId === board.value?.orgId) return !!board.value?.canEditAll
  // 项目公司指标：全公司范围可维护全部，项目公司负责人仅本公司
  return !!board.value?.editableProjects?.includes(orgId)
}
function cellOf(c: ProjectCompanyBlock, metricId: string) {
  return c.cells.find((x) => x.metricId === metricId)
}
function isDirty(orgId: string, metricId: string) {
  const k = cellKey(orgId, metricId)
  const d = draft[k]
  const b = baseline[k]
  return !!d && !!b && (d.t !== b.t || d.a !== b.a || d.c !== b.c)
}
function hasDirty(orgId: string) {
  return Object.keys(draft).some((k) => k.startsWith(`${orgId}|`) && isDirty(orgId, k.split('|')[1]))
}
function toStr(v: number | null | undefined) {
  return v === null || v === undefined ? '' : String(v)
}

function seedDraft(rows: MetricRow[], orgId: string) {
  rows.forEach((r) => {
    const k = cellKey(orgId, r.metricId)
    const value = { t: toStr(r.target), a: toStr(r.actual), c: toStr(r.collActual) }
    draft[k] = { ...value }
    baseline[k] = { ...value }
  })
}

/** 本人范围：无组织维度数据（与后端 visibleOrgs 口径一致） */
const noOrgDimension = computed(() => auth.scope === 'self')

let loadSeq = 0
async function load() {
  if (!view.period || !view.contextReady) return
  const seq = ++loadSeq
  if (noOrgDimension.value) {
    loading.value = false
    error.value = ''
    board.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await metricApi.board(view.period, view.orgId)
    // 并发加载时丢弃过期响应，避免先到的 403 覆盖后到的成功结果
    if (seq !== loadSeq) return
    board.value = data
    Object.keys(draft).forEach((k) => {
      delete draft[k]
      delete baseline[k]
    })
    seedDraft(board.value.annual, board.value.orgId)
    seedDraft(board.value.monitor, board.value.orgId)
    board.value.project.companies.forEach((c) => seedDraft(c.cells, c.orgId))
    await loadPrev()
  } catch (e) {
    if (seq !== loadSeq) return
    error.value = (e as Error).message
    board.value = null
  } finally {
    if (seq === loadSeq) loading.value = false
  }
  // 定位必须等 loading 关闭、表格真正渲染之后再做，否则查不到目标单元格
  if (seq === loadSeq) await applyFocus()
}

async function loadPrev() {
  // 监控指标的上期值：用趋势接口取倒数第二个点
  const monitor = board.value?.monitor ?? []
  await Promise.all(
    monitor.map(async (m) => {
      try {
        const t = await dashboardApi.trend(m.metricId, view.orgId)
        const pts = t.points
        prevMap[m.metricId] = pts.length >= 2 ? pts[pts.length - 2].value : NaN
      } catch {
        prevMap[m.metricId] = NaN
      }
    }),
  )
}

async function applyFocus() {
  const f = view.consumeFocus()
  if (!f) return
  await nextTick()
  // 只做定位与高亮，不改写全局组织视角：
  // 「去维护」跳到本页后，用户返回驾驶舱应仍停留在原来的组织视角上。
  const el = document.querySelector(`[data-cell="${f.orgId}:${f.metricId}"]`)
  if (!el) return
  const target = el.tagName === 'TD' ? (el.closest('tr') ?? el) : el
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  target.classList.add('row-focus')
  setTimeout(() => target.classList.remove('row-focus'), 2600)
}

function num(v: string): number | null {
  const s = String(v).trim()
  if (s === '') return null
  const n = Number(s)
  return Number.isNaN(n) ? null : n
}

async function saveRow(row: MetricRow, orgId: string) {
  const k = cellKey(orgId, row.metricId)
  const d = draft[k]
  const b = baseline[k]
  if (!d || !b) return
  saving.value = k
  try {
    if (d.t !== b.t) {
      await metricApi.saveTarget({ metric_id: row.metricId, org_id: orgId, period: view.period, value: num(d.t) })
    }
    if (d.a !== b.a) {
      await metricApi.saveActual({ metric_id: row.metricId, org_id: orgId, period: view.period, value: num(d.a) })
    }
    if (d.c !== b.c && row.collMetricId) {
      await metricApi.saveActual({ metric_id: row.collMetricId, org_id: orgId, period: view.period, value: num(d.c) })
    }
    app.toast('已保存')
    await load()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    saving.value = ''
  }
}

async function saveProject(c: ProjectCompanyBlock) {
  saving.value = c.orgId
  try {
    for (const cell of c.cells) {
      const k = cellKey(c.orgId, cell.metricId)
      const d = draft[k]
      const b = baseline[k]
      if (!d || !b) continue
      if (d.t !== b.t) {
        await metricApi.saveTarget({ metric_id: cell.metricId, org_id: c.orgId, period: view.period, value: num(d.t) })
      }
      if (d.a !== b.a) {
        await metricApi.saveActual({ metric_id: cell.metricId, org_id: c.orgId, period: view.period, value: num(d.a) })
      }
      if (d.c !== b.c && cell.collMetricId) {
        await metricApi.saveActual({ metric_id: cell.collMetricId, org_id: c.orgId, period: view.period, value: num(d.c) })
      }
    }
    app.toast('已保存')
    await load()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    saving.value = ''
  }
}

function openProjectForm(c?: ProjectCompanyBlock) {
  projectError.value = ''
  projectForm.id = c?.orgId ?? ''
  projectForm.name = c?.name ?? ''
  projectForm.head = c?.head ?? ''
  projectForm.targets = {}
  projectFormOpen.value = true
}

async function saveProjectForm() {
  projectError.value = ''
  if (!projectForm.name) {
    projectError.value = '公司名称不能为空'
    return
  }
  saving.value = 'project'
  try {
    if (projectForm.id) {
      await projectApi.update(projectForm.id, { name: projectForm.name, head: projectForm.head })
    } else {
      const year = view.period.slice(0, 4)
      const targets = Object.entries(projectForm.targets)
        .filter(([, v]) => v !== null && v !== undefined && String(v).trim() !== '' && !Number.isNaN(Number(v)))
        .map(([metric_id, value]) => ({ metric_id, value: Number(value), year }))
      await projectApi.create({ name: projectForm.name, head: projectForm.head, targets })
    }
    app.toast('已保存')
    projectFormOpen.value = false
    await load()
  } catch (e) {
    projectError.value = (e as Error).message
  } finally {
    saving.value = ''
  }
}

async function askDeleteProject(c: ProjectCompanyBlock) {
  try {
    const list = await projectApi.list()
    projectDelete.value = list.find((p) => p.id === c.orgId) ?? { id: c.orgId, name: c.name, head: c.head, parentId: 'CO', impact: { users: 0, children: 0, tasks: 0, targets: 0, actuals: 0 } }
  } catch {
    projectDelete.value = { id: c.orgId, name: c.name, head: c.head, parentId: 'CO', impact: { users: 0, children: 0, tasks: 0, targets: 0, actuals: 0 } }
  }
}

async function doDeleteProject() {
  if (!projectDelete.value) return
  try {
    await projectApi.remove(projectDelete.value.id)
    app.toast('已删除项目公司')
    projectDelete.value = null
    await load()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

async function onImport(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    importResult.value = await metricApi.importFile(file, view.period)
    importOpen.value = true
    if (importResult.value.imported) {
      app.toast(`成功导入 ${importResult.value.imported} 行`)
      await load()
    }
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    input.value = ''
  }
}

function rateClass(light: string) {
  return { green: 'text-good-600', amber: 'text-warn-600', red: 'text-bad-600', none: 'text-slate-400' }[light] ?? 'text-slate-400'
}

watch([() => view.period, () => view.orgId, () => view.contextReady], load, { immediate: true })
</script>
