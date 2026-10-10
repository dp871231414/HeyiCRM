<template>
  <div class="space-y-4">
    <!-- 工具条 -->
    <div class="card p-3.5 flex flex-wrap items-center gap-2.5">
      <input v-model.trim="keyword" class="input !w-56" placeholder="搜索任务ID / 名称 / 责任人" @keyup.enter="load" />
      <select v-model="deptFilter" class="input !w-44">
        <option value="">全部责任部门</option>
        <option v-for="o in orgs" :key="o.id" :value="o.id">{{ '　'.repeat(o.depth) }}{{ o.name }}</option>
      </select>
      <select v-model="statusFilter" class="input !w-36">
        <option value="">全部状态</option>
        <option value="done">已完成</option>
        <option value="normal">正常</option>
        <option value="due_soon">临期</option>
        <option value="overdue">逾期</option>
        <option value="risk">异常</option>
      </select>
      <button class="btn-ghost" @click="load">查询</button>

      <div class="ml-auto flex items-center gap-2">
        <button class="btn-ghost" @click="download(taskApi.templateUrl(), '重点任务导入标准模板.xlsx')">下载模板</button>
        <button class="btn-ghost" @click="download(taskApi.exportUrl(), '重点任务清单.xlsx')">导出</button>
        <label v-if="auth.hasPerm('task.import')" class="btn-ghost cursor-pointer">
          批量导入
          <input type="file" accept=".xlsx" class="hidden" @change="onImport" />
        </label>
        <button v-if="auth.hasPerm('task.edit')" class="btn-primary" @click="openForm()">新建任务</button>
      </div>
    </div>

    <!-- 汇总 -->
    <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500 px-1">
      <span>共 <b class="text-slate-800">{{ total }}</b> 项任务</span>
      <span>已完成 <b class="text-good-600">{{ countBy('done') }}</b></span>
      <span>临期 <b class="text-warn-600">{{ countBy('due_soon') }}</b></span>
      <span>逾期 <b class="text-bad-600">{{ countBy('overdue') }}</b></span>
      <span>异常 <b class="text-bad-600">{{ countBy('risk') }}</b></span>
    </div>

    <!-- 表格 -->
    <div class="card overflow-hidden">
      <div v-if="loading" class="p-10 text-center text-slate-400 text-sm">加载中…</div>
      <div v-else-if="!tasks.length" class="p-10 text-center text-slate-400 text-sm">暂无任务</div>
      <div v-else class="overflow-x-auto">
        <table class="table-freeze w-full min-w-[1360px]">
          <thead>
            <tr class="border-b border-slate-200">
              <th class="th col-id w-[96px]">任务ID</th>
              <th class="th col-name w-[240px]">任务名称</th>
              <th class="th w-[140px]">任务分类</th>
              <th class="th w-[100px]">责任人</th>
              <th class="th w-[120px]">责任部门</th>
              <th class="th w-[100px] text-right">目标</th>
              <th class="th w-[110px] text-right">已完成</th>
              <th class="th w-[130px]">完成进度</th>
              <th class="th w-[180px]">计划起止</th>
              <th class="th w-[110px]">状态</th>
              <th class="th col-ops w-[120px] text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in tasks" :key="t.id" class="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td class="td col-id font-mono text-xs text-slate-500">{{ t.id }}</td>
              <td class="td col-name">
                <div class="font-semibold text-slate-800 truncate" :title="t.parent">{{ t.parent }}</div>
              </td>
              <td class="td text-slate-500">{{ t.title || '—' }}</td>
              <td class="td">{{ t.owner }}</td>
              <td class="td">{{ t.deptName }}</td>
              <td class="td text-right font-mono">{{ fmt(t.target) }}<span class="text-[11px] text-slate-400 ml-0.5">{{ t.unit }}</span></td>
              <td class="td text-right font-mono">{{ fmt(t.done) }}</td>
              <td class="td">
                <div class="flex items-center gap-2">
                  <div class="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden min-w-[46px]">
                    <div class="h-full rounded-full" :class="progressBar(t)" :style="{ width: Math.min(100, t.progress) + '%' }" />
                  </div>
                  <span class="text-xs font-bold text-slate-600 w-9 text-right">{{ t.progress }}%</span>
                </div>
              </td>
              <td class="td text-xs text-slate-500">{{ t.startDate }} ~ {{ t.endDate }}</td>
              <td class="td"><StatusBadge :status="t.statusLevel" :text="t.statusLabel" /></td>
              <td class="td col-ops text-right">
                <button v-if="auth.hasPerm('task.edit')" class="btn-ghost btn-sm" @click="openForm(t)">编辑</button>
                <button
                  v-if="auth.hasPerm('task.delete')"
                  class="btn-danger btn-sm ml-1.5"
                  @click="confirmDelete(t)"
                >
                  删除
                </button>
                <span v-if="!auth.hasAnyPerm(['task.edit', 'task.delete'])" class="text-xs text-slate-300">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 新建 / 编辑 -->
    <ModalDialog :open="formOpen" :title="form.id ? '编辑任务' : '新建任务'" width="lg" @close="formOpen = false">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="md:col-span-2">
          <label class="label">任务名称（一级任务）</label>
          <input v-model.trim="form.parent" class="input" placeholder="如：完成全年营收目标 10.2 亿" />
        </div>
        <div>
          <label class="label">任务分类（二级任务）</label>
          <input v-model.trim="form.title" class="input" placeholder="如：华东大区营收达成（可留空）" />
        </div>
        <div>
          <label class="label">责任人</label>
          <select v-model="form.owner" class="input">
            <option v-for="o in owners" :key="o.id" :value="o.name">{{ o.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">责任部门</label>
          <select v-model="form.deptId" class="input">
            <option v-for="o in orgs" :key="o.id" :value="o.id">{{ '　'.repeat(o.depth) }}{{ o.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">是否异常</label>
          <select v-model="form.abnormal" class="input">
            <option :value="false">否</option>
            <option :value="true">是</option>
          </select>
        </div>
        <div>
          <label class="label">目标（数字，非量化任务填 1）</label>
          <input v-model.number="form.target" type="number" class="input" />
        </div>
        <div>
          <label class="label">已完成（非量化任务未完成 0 / 完成 1）</label>
          <input v-model.number="form.done" type="number" class="input" />
        </div>
        <div>
          <label class="label">数量单位</label>
          <input v-model.trim="form.unit" class="input" placeholder="万元 / 辆 / 项 / %" />
        </div>
        <div>
          <label class="label">完成进度（系统计算）</label>
          <input class="input" :value="previewProgress + '%'" disabled />
        </div>
        <div>
          <label class="label">计划开始日期</label>
          <input v-model="form.startDate" type="date" class="input" />
        </div>
        <div>
          <label class="label">计划结束日期</label>
          <input v-model="form.endDate" type="date" class="input" />
        </div>
        <div class="md:col-span-2">
          <label class="label">任务描述</label>
          <textarea v-model="form.description" rows="2" class="input" />
        </div>
        <div class="md:col-span-2">
          <label class="label">进展描述</label>
          <textarea v-model="form.note" rows="2" class="input" />
        </div>
      </div>
      <p v-if="formError" class="mt-3 text-sm text-bad-600">{{ formError }}</p>
      <template #footer>
        <button class="btn-ghost" @click="formOpen = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
      </template>
    </ModalDialog>

    <!-- 删除确认 -->
    <ModalDialog :open="!!deleteTarget" title="确认删除任务" width="sm" @close="deleteTarget = null">
      <p class="text-sm text-slate-600">
        将删除任务「{{ deleteTarget?.parent }}」（{{ deleteTarget?.id }}）。该操作不可撤销。
      </p>
      <template #footer>
        <button class="btn-ghost" @click="deleteTarget = null">取消</button>
        <button class="btn-danger" @click="doDelete">确认删除</button>
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
            <thead class="sticky top-0">
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
import { computed, onMounted, reactive, ref } from 'vue'

import { downloadFile, metaApi, taskApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { ImportResult, TaskItem } from '@/types'
import { fmt } from '@/utils/format'

const auth = useAuthStore()
const app = useAppStore()

const tasks = ref<TaskItem[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const deptFilter = ref('')
const statusFilter = ref('')
const orgs = ref<{ id: string; name: string; depth: number }[]>([])
const owners = ref<{ id: string; name: string }[]>([])

const formOpen = ref(false)
const saving = ref(false)
const formError = ref('')
const form = reactive({
  id: '',
  parent: '',
  title: '',
  description: '',
  abnormal: false,
  target: 1,
  done: 0,
  unit: '',
  note: '',
  startDate: new Date().toISOString().slice(0, 10),
  endDate: '',
  deptId: '',
  owner: '',
})

const deleteTarget = ref<TaskItem | null>(null)
const importOpen = ref(false)
const importResult = ref<ImportResult | null>(null)

const previewProgress = computed(() =>
  form.target > 0 ? Math.round((form.done / form.target) * 100) : 0,
)

function countBy(level: string) {
  return tasks.value.filter((t) => t.statusLevel === level).length
}
function progressBar(t: TaskItem) {
  if (t.statusLevel === 'overdue' || t.statusLevel === 'risk') return 'bg-bad-500'
  if (t.statusLevel === 'due_soon') return 'bg-warn-500'
  if (t.statusLevel === 'done') return 'bg-good-500'
  return 'bg-brand-500'
}
const download = downloadFile

async function load() {
  loading.value = true
  try {
    const res = await taskApi.list({
      keyword: keyword.value,
      dept_id: deptFilter.value,
      status: statusFilter.value,
      size: 500,
    })
    tasks.value = res.items
    total.value = res.total
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    loading.value = false
  }
}

function openForm(t?: TaskItem) {
  formError.value = ''
  if (t) {
    Object.assign(form, {
      id: t.id,
      parent: t.parent,
      title: t.title ?? '',
      description: t.description,
      abnormal: t.abnormal,
      target: Number(t.target),
      done: Number(t.done),
      unit: t.unit,
      note: t.note,
      startDate: t.startDate,
      endDate: t.endDate,
      deptId: t.deptId,
      owner: t.owner,
    })
  } else {
    Object.assign(form, {
      id: '',
      parent: '',
      title: '',
      description: '',
      abnormal: false,
      target: 1,
      done: 0,
      unit: '',
      note: '',
      startDate: new Date().toISOString().slice(0, 10),
      endDate: '',
      deptId: orgs.value[1]?.id ?? 'CO',
      owner: owners.value[0]?.name ?? '',
    })
  }
  formOpen.value = true
}

async function save() {
  formError.value = ''
  if (!form.parent) return (formError.value = '任务名称不能为空')
  if (!(form.target > 0)) return (formError.value = '目标必须为正数')
  if (!form.endDate) return (formError.value = '请选择计划结束日期')
  if (form.endDate < form.startDate) return (formError.value = '计划结束日期不能早于开始日期')

  saving.value = true
  const payload = { ...form }
  try {
    if (form.id) await taskApi.update(form.id, payload)
    else await taskApi.create(payload)
    app.toast('保存成功')
    formOpen.value = false
    await load()
  } catch (e) {
    formError.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

function confirmDelete(t: TaskItem) {
  deleteTarget.value = t
}

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    await taskApi.remove(deleteTarget.value.id)
    app.toast('已删除')
    deleteTarget.value = null
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
    importResult.value = await taskApi.importFile(file)
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

onMounted(async () => {
  try {
    ;[orgs.value, owners.value] = await Promise.all([metaApi.orgs(), metaApi.owners()])
  } catch {
    /* 忽略字典加载失败 */
  }
  await load()
})
</script>
