<template>
  <div class="space-y-4">
    <!-- 工具条 -->
    <div class="card p-3.5 flex items-center gap-2.5">
      <h2 class="text-[15px] font-extrabold text-slate-900">数据字典</h2>
      <span class="text-xs text-slate-400">系统配置 · 维护车辆型号、挂车型号等可选项</span>
      <div class="ml-auto">
        <button v-if="auth.hasPerm('sys.config.edit')" class="btn-primary" @click="openForm()">新增字典</button>
      </div>
    </div>

    <div v-if="loading" class="card p-10 text-center text-slate-400 text-sm">加载中…</div>
    <div v-else-if="!dicts.length" class="card p-10 text-center text-slate-400 text-sm">暂无字典，点击右上角「新增字典」创建。</div>

    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div v-for="d in dicts" :key="d.id" class="card p-4">
        <div class="flex items-start gap-3">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="text-sm font-bold text-slate-800">{{ d.name }}</span>
              <span v-if="d.code" class="chip bg-slate-100 text-slate-500 border border-slate-200">{{ d.code }}</span>
              <span
                class="chip"
                :class="d.status === 'disabled' ? 'bg-slate-100 text-slate-400 border border-slate-200' : 'bg-good-50 text-good-700 border border-good-100'"
              >
                {{ d.status === 'disabled' ? '已停用' : '启用' }}
              </span>
            </div>
            <div v-if="d.items.length" class="mt-3 flex flex-wrap gap-2">
              <span v-for="it in d.items" :key="it.id" class="chip bg-brand-50 text-brand-700 border border-brand-100">
                {{ it.value }}
              </span>
            </div>
            <p v-else class="mt-2 text-xs text-slate-400">（暂无枚举值）</p>
          </div>
          <div v-if="auth.hasPerm('sys.config.edit')" class="flex items-center gap-1.5 shrink-0">
            <button class="btn-ghost btn-sm" @click="openForm(d)">编辑</button>
            <button
              v-if="d.status !== 'disabled'"
              class="btn-ghost btn-sm text-amber-600 hover:bg-amber-50"
              @click="toggleStatus(d, 'disabled')"
            >
              停用
            </button>
            <button v-else class="btn-ghost btn-sm text-good-700 hover:bg-good-50" @click="toggleStatus(d, 'active')">
              启用
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增 / 编辑字典 -->
    <ModalDialog :open="formOpen" :title="form.id ? '编辑字典' : '新增字典'" width="lg" @close="formOpen = false">
      <div class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="label">字典名称<span class="req">*</span></label>
            <input v-model.trim="form.name" class="input" placeholder="如：车辆型号" />
          </div>
          <div>
            <label class="label">编码<span class="text-slate-400 font-normal">（可选，前端按编码取值）</span></label>
            <input v-model.trim="form.code" class="input" placeholder="如：vehicle_model" />
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="label !mb-0">字典枚举值<span class="req">*</span><span class="text-slate-400 font-normal">（可新增多个）</span></label>
            <button v-if="auth.hasPerm('sys.config.edit')" class="btn-ghost btn-sm" @click="addItem">+ 添加枚举值</button>
          </div>
          <div v-if="!form.items.length" class="text-xs text-slate-400 py-3 text-center border border-dashed border-slate-200 rounded-lg">
            暂无枚举值，点击「添加枚举值」新增
          </div>
          <div v-else class="space-y-2">
            <div v-for="(it, i) in form.items" :key="i" class="flex items-center gap-2">
              <span class="w-6 text-center text-xs text-slate-400 shrink-0">{{ i + 1 }}</span>
              <input v-model.trim="it.value" class="input flex-1" placeholder="枚举值，如：6*4牵引车" />
              <input
                v-model.number="it.sort"
                type="number"
                class="input w-20 shrink-0"
                title="排序（升序）"
                placeholder="排序"
              />
              <button class="btn-ghost btn-sm shrink-0" @click="form.items.splice(i, 1)">删除</button>
            </div>
          </div>
        </div>

        <p v-if="formError" class="text-sm text-bad-600">{{ formError }}</p>
      </div>
      <template #footer>
        <button class="btn-ghost" @click="formOpen = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
      </template>
    </ModalDialog>

    <!-- 停用确认 -->
    <ModalDialog :open="!!pendingDisable" title="确认停用字典" width="sm" @close="pendingDisable = null">
      <p class="text-sm text-slate-600">
        停用字典「{{ pendingDisable?.name }}」后，其枚举值将不再出现在关联下拉（如项目需求中的电池容量）。
        已存在配置不会被删除，可随时重新启用。
      </p>
      <template #footer>
        <button class="btn-ghost" @click="pendingDisable = null">取消</button>
        <button class="btn-primary" :disabled="toggling" @click="confirmToggle">
          {{ toggling ? '处理中…' : '确认停用' }}
        </button>
      </template>
    </ModalDialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { dictApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { SysDict } from '@/types'

const auth = useAuthStore()
const app = useAppStore()

const dicts = ref<SysDict[]>([])
const loading = ref(false)
const formOpen = ref(false)
const saving = ref(false)
const formError = ref('')
const form = reactive<{ id: number | null; name: string; code: string; items: { value: string; sort: number }[] }>({
  id: null,
  name: '',
  code: '',
  items: [],
})
const pendingDisable = ref<SysDict | null>(null)
const toggling = ref(false)

async function load() {
  loading.value = true
  try {
    dicts.value = await dictApi.list()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    loading.value = false
  }
}

function addItem() {
  form.items.push({ value: '', sort: form.items.length })
}

function openForm(d?: SysDict) {
  formError.value = ''
  if (d) {
    Object.assign(form, {
      id: d.id,
      name: d.name,
      code: d.code || '',
      items: d.items.map((it) => ({ value: it.value, sort: it.sort })),
    })
  } else {
    Object.assign(form, { id: null, name: '', code: '', items: [] })
  }
  formOpen.value = true
}

async function save() {
  formError.value = ''
  if (!form.name) return (formError.value = '字典名称不能为空')
  const hasValue = form.items.some((it) => it.value.trim())
  if (!hasValue) return (formError.value = '请至少填写一个字典枚举值')
  saving.value = true
  const payload = {
    name: form.name,
    code: form.code || null,
    items: form.items
      .filter((it) => it.value.trim())
      .map((it, i) => ({ value: it.value.trim(), sort: Number(it.sort) || i })),
  }
  try {
    if (form.id) await dictApi.update(form.id, payload)
    else await dictApi.create(payload)
    app.toast('保存成功')
    formOpen.value = false
    await load()
  } catch (e) {
    formError.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

/** 启用/停用：停用需二次确认（pendingDisable 弹窗），启用直接执行 */
function toggleStatus(d: SysDict, status: 'active' | 'disabled') {
  if (status === 'disabled') {
    pendingDisable.value = d
    return
  }
  void doToggle(d, 'active')
}

async function doToggle(d: SysDict, status: 'active' | 'disabled') {
  toggling.value = true
  try {
    await dictApi.setStatus(d.id, status)
    app.toast(status === 'disabled' ? '已停用' : '已启用')
    await load()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    toggling.value = false
  }
}

async function confirmToggle() {
  if (!pendingDisable.value) return
  const d = pendingDisable.value
  pendingDisable.value = null
  await doToggle(d, 'disabled')
}

onMounted(load)
</script>
