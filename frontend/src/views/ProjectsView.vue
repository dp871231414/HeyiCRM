<template>
  <div class="space-y-4">
    <!-- 工具条 -->
    <div class="card p-3.5 flex flex-wrap items-center gap-2.5">
      <input v-model.trim="keyword" class="input !w-56" placeholder="搜索项目ID / 名称 / 负责人" @keyup.enter="applyFilters" />
      <select v-model="stageFilter" class="input !w-44" @change="applyFilters">
        <option value="">全部阶段</option>
        <option v-for="s in STAGES" :key="s" :value="s">{{ s }}% {{ MARKET_STAGE_LABELS[s] }}</option>
      </select>
      <button class="btn-ghost" @click="applyFilters">查询</button>

      <div class="ml-auto flex items-center gap-2">
        <!-- 行高设置：按账号记忆，下次登录仍生效 -->
        <div class="flex items-center gap-1.5">
          <span class="text-xs text-slate-400">行高</span>
          <select v-model="rowHeightSel" class="input !w-32" @change="onRowHeightChange">
            <option value="default">默认</option>
            <option value="high">高（2X）</option>
            <option value="ultra">超高（3X）</option>
          </select>
        </div>
        <button v-if="auth.hasPerm('market.edit')" class="btn-ghost" @click="confirmReseed = true">重新生成</button>
        <button v-if="auth.hasPerm('market.edit')" class="btn-primary" @click="openForm()">新建项目</button>
      </div>
    </div>

    <!-- 汇总 -->
    <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500 px-1">
      <span>共 <b class="text-slate-800">{{ total }}</b> 个项目</span>
      <span>牵引车需求 <b class="text-brand-600">{{ sumOf('tractorDemand') }}</b> 辆</span>
      <span>挂车需求 <b class="text-brand-600">{{ sumOf('trailerDemand') }}</b> 辆</span>
      <span class="text-slate-400">列表按数据可见范围展示（创建人归属部门匹配）</span>
    </div>

    <!-- 表格 -->
    <div class="card overflow-hidden">
      <div v-if="loading" class="p-10 text-center text-slate-400 text-sm">加载中…</div>
      <div v-else-if="!projects.length" class="p-10 text-center text-slate-400 text-sm">暂无项目</div>
      <div v-else class="overflow-x-auto">
        <table :class="rowHeightClass" class="w-full min-w-[1960px]">
          <thead>
            <tr class="border-b border-slate-200">
              <th class="th w-[90px]">项目ID</th>
              <th class="th w-[320px]">项目名称</th>
              <th class="th w-[460px]">项目描述</th>
              <th class="th w-[110px] text-right">牵引车需求</th>
              <th class="th w-[100px] text-right">挂车需求</th>
              <th class="th w-[150px]">项目阶段</th>
              <th class="th w-[90px]">负责人</th>
              <th class="th w-[120px]">所属部门</th>
              <th class="th w-[90px]">创建人</th>
              <th class="th w-[140px]">创建时间</th>
              <th class="th w-[140px]">更新时间</th>
              <th class="th w-[120px] text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in projects" :key="p.id" class="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td class="td font-mono text-xs text-slate-500">{{ p.id }}</td>
              <td class="td w-[320px]">
                <div class="cell-c font-semibold text-slate-800" :title="p.name">{{ p.name }}</div>
              </td>
              <td class="td w-[460px]">
                <div class="cell-c text-slate-500" :title="p.description || '—'">{{ p.description || '—' }}</div>
              </td>
              <td class="td text-right font-mono">{{ p.tractorDemand }}<span class="text-[11px] text-slate-400 ml-0.5">辆</span></td>
              <td class="td text-right font-mono">{{ p.trailerDemand }}<span class="text-[11px] text-slate-400 ml-0.5">辆</span></td>
              <td class="td">
                <span class="chip border" :class="STAGE_CHIP[p.stage]">{{ p.stage }}% {{ p.stageLabel }}</span>
              </td>
              <td class="td">{{ p.owner }}</td>
              <td class="td text-slate-500">{{ p.ownerDeptName || '—' }}</td>
              <td class="td text-slate-500">{{ p.createdByName || '—' }}</td>
              <td class="td text-xs text-slate-500">{{ fmtTime(p.createdAt) }}</td>
              <td class="td text-xs text-slate-500">{{ fmtTime(p.updatedAt) }}</td>
              <td class="td text-right">
                <button v-if="auth.hasPerm('market.edit')" class="btn-ghost btn-sm" @click="openForm(p)">编辑</button>
                <button
                  v-if="auth.hasPerm('market.delete')"
                  class="btn-danger btn-sm ml-1.5"
                  @click="deleteTarget = p"
                >
                  删除
                </button>
                <span v-if="!auth.hasAnyPerm(['market.edit', 'market.delete'])" class="text-xs text-slate-300">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- 分页器：始终显示（与任务管理一致） -->
      <div class="flex items-center justify-between border-t border-slate-100 px-3.5 py-2.5">
        <span class="text-xs text-slate-400">每页最多 {{ PAGE_SIZE }} 条</span>
        <PaginationBar :page="page" :page-count="pageCount" :total="total" @update:page="goPage" />
      </div>
    </div>

    <!-- 新建 / 编辑 -->
    <ModalDialog :open="formOpen" :title="form.id ? '编辑项目' : '新建项目'" width="lg" @close="formOpen = false">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="md:col-span-2">
          <label class="label">项目名称</label>
          <input v-model.trim="form.name" class="input" placeholder="如：华东物流园运力替换项目" />
        </div>
        <div>
          <label class="label">项目阶段<span class="req">*</span></label>
          <select v-model.number="form.stage" class="input">
            <option v-for="s in STAGES" :key="s" :value="s">{{ s }}% {{ MARKET_STAGE_LABELS[s] }}</option>
          </select>
        </div>
        <div>
          <label class="label">负责人<span class="req">*</span></label>
          <select v-model="form.owner" class="input" @change="onOwnerChange">
            <option value="" disabled>请选择负责人</option>
            <option v-for="o in marketOwners" :key="o.id" :value="o.name">{{ o.name }}（{{ o.deptName }}）</option>
          </select>
        </div>
        <div>
          <label class="label">所属部门<span class="text-slate-400 font-normal">（选负责人后自动带出）</span></label>
          <input :value="form.ownerDeptName" class="input bg-slate-50" disabled placeholder="选择负责人后自动带出" />
        </div>
        <div>
          <label class="label">牵引车需求数（辆）</label>
          <input v-model.number="form.tractorDemand" type="number" min="0" class="input" placeholder="如：30" />
        </div>
        <div>
          <label class="label">挂车需求数（辆）</label>
          <input v-model.number="form.trailerDemand" type="number" min="0" class="input" placeholder="如：15" />
        </div>
        <div class="md:col-span-2">
          <label class="label">项目描述<span class="text-slate-400 font-normal">（选填）</span></label>
          <textarea v-model="form.description" rows="3" class="input" />
        </div>
      </div>
      <p class="mt-3 text-[11px] text-slate-400">创建人、创建时间、更新时间由系统自动记录，无需填写。</p>
      <p v-if="formError" class="mt-2 text-sm text-bad-600">{{ formError }}</p>
      <template #footer>
        <button class="btn-ghost" @click="formOpen = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
      </template>
    </ModalDialog>

    <!-- 删除确认 -->
    <ModalDialog :open="!!deleteTarget" title="确认删除项目" width="sm" @close="deleteTarget = null">
      <p class="text-sm text-slate-600">
        将删除项目「{{ deleteTarget?.name }}」（{{ deleteTarget?.id }}）。该操作不可撤销，驾驶舱漏斗会同步减少。
      </p>
      <template #footer>
        <button class="btn-ghost" @click="deleteTarget = null">取消</button>
        <button class="btn-danger" @click="doDelete">确认删除</button>
      </template>
    </ModalDialog>

    <!-- 重新生成确认 -->
    <ModalDialog :open="confirmReseed" title="重新生成项目数据" width="sm" @close="confirmReseed = false">
      <p class="text-sm text-slate-600">
        将删除全部现有市场项目，并按当前「市场部及其下属部门」人员清单重新生成。该操作不可撤销。
      </p>
      <template #footer>
        <button class="btn-ghost" @click="confirmReseed = false">取消</button>
        <button class="btn-danger" :disabled="reseeding" @click="doReseed">
          {{ reseeding ? '生成中…' : '确认重新生成' }}
        </button>
      </template>
    </ModalDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { marketApi, metaApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { MARKET_STAGE_LABELS, type MarketOwner, type MarketProjectItem, type MarketStage } from '@/types'

const auth = useAuthStore()
const app = useAppStore()

/** 行高：绑定账号偏好（default/high/ultra），切换后写入后端、下次登录仍生效 */
const rowHeightSel = ref<'default' | 'high' | 'ultra'>((auth.rowHeight as 'default' | 'high' | 'ultra') || 'default')
const rowHeightClass = computed(() => `rh-${rowHeightSel.value}`)
function onRowHeightChange() {
  auth.updatePreferences({ rowHeight: rowHeightSel.value }).catch(() => {})
}

const STAGES: MarketStage[] = [10, 25, 50, 75, 90, 100]

/** 系统默认市场部 ID · 与后端 DEFAULT_MARKET_DEPT_ID 对应（用于负责人范围提示文案） */
const MARKET_DEPT_ID = 'D01'

/** 阶段徽章配色：由浅入深，与驾驶舱漏斗色阶一致 */
const STAGE_CHIP: Record<number, string> = {
  10: 'bg-slate-100 text-slate-600 border-slate-200',
  25: 'bg-brand-50 text-brand-700 border-brand-100',
  50: 'bg-brand-50 text-brand-700 border-brand-100',
  75: 'bg-brand-100 text-brand-700 border-brand-200',
  90: 'bg-brand-100 text-brand-800 border-brand-200',
  100: 'bg-good-50 text-good-700 border-good-100',
}

const projects = ref<MarketProjectItem[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const stageFilter = ref<number | ''>('')
/** 负责人候选：仅市场部及其下属部门内的启用账号 */
const marketOwners = ref<MarketOwner[]>([])

const PAGE_SIZE = 50
const page = ref(1)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function sumOf(field: 'tractorDemand' | 'trailerDemand') {
  return projects.value.reduce((acc, p) => acc + (p[field] || 0), 0)
}

/** ISO 时间 → 本地可读格式（与任务管理同一套） */
function fmtTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const formOpen = ref(false)
const saving = ref(false)
const formError = ref('')
const form = reactive({
  id: '',
  name: '',
  description: '',
  stage: 10 as MarketStage,
  owner: '',
  ownerDeptId: '',
  ownerDeptName: '',
  tractorDemand: 0,
  trailerDemand: 0,
})
const deleteTarget = ref<MarketProjectItem | null>(null)
const confirmReseed = ref(false)
const reseeding = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await marketApi.list({
      keyword: keyword.value,
      stage: stageFilter.value,
      page: page.value,
      size: PAGE_SIZE,
    })
    projects.value = res.items
    total.value = res.total
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  load()
}

function goPage(n: number) {
  const next = Math.min(Math.max(1, n), pageCount.value)
  if (next === page.value) return
  page.value = next
  load()
}

function openForm(p?: MarketProjectItem) {
  formError.value = ''
  if (p) {
    const owner = marketOwners.value.find((o) => o.name === p.owner)
    Object.assign(form, {
      id: p.id,
      name: p.name,
      description: p.description,
      stage: p.stage,
      owner: p.owner,
      ownerDeptId: p.ownerDeptId ?? owner?.deptId ?? '',
      ownerDeptName: p.ownerDeptName || owner?.deptName || '',
      tractorDemand: p.tractorDemand,
      trailerDemand: p.trailerDemand,
    })
  } else {
    const first = marketOwners.value[0]
    Object.assign(form, {
      id: '',
      name: '',
      description: '',
      stage: 10,
      owner: first?.name ?? auth.user?.name ?? '',
      ownerDeptId: first?.deptId ?? MARKET_DEPT_ID,
      ownerDeptName: first?.deptName ?? '',
      tractorDemand: 0,
      trailerDemand: 0,
    })
  }
  formOpen.value = true
}

/** 选择负责人后，自动带出其直接所属部门（二级/三级部门均可） */
function onOwnerChange() {
  const o = marketOwners.value.find((x) => x.name === form.owner)
  form.ownerDeptId = o?.deptId ?? ''
  form.ownerDeptName = o?.deptName ?? ''
}

async function save() {
  formError.value = ''
  if (!form.name) return (formError.value = '项目名称不能为空')
  if (!(form.tractorDemand >= 0) || !(form.trailerDemand >= 0)) return (formError.value = '需求数不能为负')
  if (!form.owner) return (formError.value = '请选择负责人')
  if (!form.ownerDeptId) return (formError.value = '请选择市场部及下属部门的负责人')

  saving.value = true
  // 请求体使用后端约定的 snake_case 字段
  const payload = {
    name: form.name,
    description: form.description,
    tractor_demand: form.tractorDemand,
    trailer_demand: form.trailerDemand,
    stage: form.stage,
    owner: form.owner,
    owner_dept_id: form.ownerDeptId,
  }
  try {
    if (form.id) await marketApi.update(form.id, payload)
    else await marketApi.create(payload)
    app.toast('保存成功')
    formOpen.value = false
    await load()
  } catch (e) {
    formError.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    await marketApi.remove(deleteTarget.value.id)
    app.toast('已删除')
    deleteTarget.value = null
    await load()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

async function doReseed() {
  reseeding.value = true
  try {
    const r = await marketApi.reseed()
    app.toast(r.msg || '已重新生成项目数据')
    confirmReseed.value = false
    await load()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    reseeding.value = false
  }
}

onMounted(async () => {
  try {
    marketOwners.value = await metaApi.marketOwners()
  } catch {
    /* 忽略字典加载失败 */
  }
  await load()
})
</script>
