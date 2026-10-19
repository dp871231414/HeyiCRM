<template>
  <div class="lg:flex lg:gap-4">
    <!-- 左：文档列表（按分组归类） -->
    <aside class="lg:w-64 lg:shrink-0 card p-3 mb-4 lg:mb-0">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-semibold text-slate-700">文档中心</h2>
        <div class="flex items-center gap-1.5">
          <button v-if="canCreate" class="btn-ghost btn-sm" @click="openCreate">新建</button>
          <button v-if="canSync" class="btn-ghost btn-sm" :disabled="syncing" @click="syncAll">
            {{ syncing ? '同步中…' : '同步' }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="text-slate-400 text-sm py-4">加载中…</div>
      <div v-else class="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
        <div v-for="grp in groupedDocs" :key="grp.name">
          <div class="px-3 mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{{ grp.name }}</div>
          <ul class="space-y-1">
            <li v-for="d in grp.docs" :key="d.key">
              <button
                class="w-full text-left px-3 py-2 rounded-lg text-sm transition"
                :class="
                  selected?.key === d.key
                    ? 'bg-brand-50 text-brand-700 font-medium'
                    : 'text-slate-600 hover:bg-slate-50'
                "
                @click="select(d)"
              >
                {{ d.title }}
                <span class="block text-[11px] text-slate-400">v{{ d.version }} · {{ fmtTime(d.updatedAt) }}</span>
              </button>
            </li>
          </ul>
        </div>
        <div v-if="!groupedDocs.length" class="text-xs text-slate-400 px-1">该账号无可见文档</div>
      </div>
      <p class="mt-3 text-[11px] text-slate-400 leading-snug">
        文档按分组归类；可见范围由角色「文档分组」权限决定。内容随系统迭代自动同步至数据库。
      </p>
    </aside>

    <!-- 右：内容 -->
    <section class="flex-1 card p-6 min-h-[60vh]">
      <div v-if="loading" class="text-slate-400 text-sm">加载中…</div>
      <div v-else-if="!selected" class="text-slate-400 text-sm">请选择左侧文档</div>
      <div v-else>
        <div class="mb-4 flex items-center gap-3 flex-wrap">
          <h1 class="text-xl font-bold text-slate-800">{{ selected.title }}</h1>
          <span class="text-xs text-slate-400">分组 · {{ selected.group }}</span>
          <span class="text-xs text-slate-400">版本 v{{ selected.version }} · 更新于 {{ fmtTime(selected.updatedAt) }}</span>
          <span
            v-if="selected.fmt === 'html'"
            class="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500"
            >富文本</span
          >
          <span
            v-else
            class="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500"
            >Markdown</span
          >
          <button v-if="canEdit && !editing" class="btn-ghost btn-sm ml-auto" @click="startEdit">编辑</button>
        </div>

        <!-- 编辑态：内容编辑区上方增加「分组」与「命名」 -->
        <div v-if="editing">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <div>
              <label class="label">分组<span class="req">*</span></label>
              <select v-model="editGroup" class="input">
                <option v-for="g in groupOptions" :key="g" :value="g">{{ g }}</option>
              </select>
            </div>
            <div>
              <label class="label">文档命名<span class="req">*</span></label>
              <input v-model.trim="editTitle" class="input" placeholder="文档标题" />
            </div>
          </div>
          <p class="text-[11px] text-slate-400 mb-2">修改命名不影响后台文档 ID（key 不变），已有链接仍有效。</p>
          <textarea v-model="editContent" class="input w-full h-72 font-mono text-xs leading-relaxed"></textarea>
          <div class="mt-2 flex gap-2">
            <button class="btn-primary btn-sm" :disabled="saving" @click="saveEdit">
              {{ saving ? '保存中…' : '保存' }}
            </button>
            <button class="btn-ghost btn-sm" @click="editing = false">取消</button>
          </div>
        </div>

        <!-- 阅读态 -->
        <div v-else>
          <iframe
            v-if="selected.fmt === 'html'"
            :srcdoc="selected.html || ''"
            class="w-full h-[76vh] border-0"
            title="document"
          ></iframe>
          <div v-else class="doc-prose" v-html="selected.html || ''"></div>
        </div>
      </div>
    </section>
  </div>

  <!-- 新建文档 -->
  <ModalDialog :open="createOpen" title="新建文档" width="lg" @close="createOpen = false">
    <div class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="label">文档命名<span class="req">*</span></label>
          <input v-model.trim="createForm.title" class="input" placeholder="如：接口联调说明" />
        </div>
        <div>
          <label class="label">分组<span class="req">*</span></label>
          <select v-model="createForm.group" class="input">
            <option v-for="g in groupOptions" :key="g" :value="g">{{ g }}</option>
          </select>
        </div>
        <div class="md:col-span-2">
          <label class="label">文档 ID（key）</label>
          <input
            v-model.trim="createForm.key"
            class="input font-mono"
            placeholder="留空自动生成（doc_xxxxxx）；仅小写字母、数字、下划线"
          />
        </div>
        <div class="md:col-span-2">
          <label class="label">格式</label>
          <select v-model="createForm.fmt" class="input">
            <option value="markdown">Markdown</option>
            <option value="html">富文本 HTML</option>
          </select>
        </div>
      </div>
      <div>
        <label class="label">内容</label>
        <textarea v-model="createForm.content" class="input w-full h-48 font-mono text-xs leading-relaxed" placeholder="文档正文，支持 Markdown / HTML"></textarea>
      </div>
      <p v-if="createError" class="text-sm text-bad-600">{{ createError }}</p>
    </div>
    <template #footer>
      <button class="btn-ghost" @click="createOpen = false">取消</button>
      <button class="btn-primary" :disabled="creating" @click="submitCreate">{{ creating ? '创建中…' : '创建' }}</button>
    </template>
  </ModalDialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { dictApi, docApi } from '@/api'
import type { SystemDoc } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import ModalDialog from '@/components/ModalDialog.vue'

const auth = useAuthStore()
const app = useAppStore()

const docs = ref<SystemDoc[]>([])
const selected = ref<SystemDoc | null>(null)
const loading = ref(false)
const syncing = ref(false)
const editing = ref(false)
const editContent = ref('')
const editTitle = ref('')
const editGroup = ref('默认文档')
const saving = ref(false)

const canEdit = computed(() => auth.hasPerm('doc.edit'))
const canCreate = computed(() => auth.hasPerm('doc.create'))
const canSync = computed(() => auth.hasPerm('doc.sync'))

// 分组字典（doc_group）取值，用于下拉与左侧分组排序
const groupOptions = ref<string[]>(['默认文档', '用户文档', '开发文档'])

const groupedDocs = computed(() => {
  const map = new Map<string, SystemDoc[]>()
  for (const d of docs.value) {
    if (!map.has(d.group)) map.set(d.group, [])
    map.get(d.group)!.push(d)
  }
  // 先按字典顺序排已知分组，再补上其余分组
  const ordered = [...groupOptions.value.filter((g) => map.has(g)), ...[...map.keys()].filter((g) => !groupOptions.value.includes(g))]
  return ordered.map((name) => ({ name, docs: map.get(name)! }))
})

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function loadGroups() {
  try {
    const dicts = await dictApi.list('doc_group')
    const d = dicts.find((x) => x.code === 'doc_group')
    if (d && d.items.length) groupOptions.value = d.items.map((i) => i.value)
  } catch {
    /* 字典取不到时用默认值 */
  }
}

async function loadList() {
  loading.value = true
  try {
    docs.value = await docApi.list()
    if (!selected.value && docs.value.length) {
      await select(docs.value[0])
    } else if (selected.value) {
      const fresh = docs.value.find((d) => d.key === selected.value!.key)
      if (fresh) selected.value = fresh
    }
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    loading.value = false
  }
}

async function select(d: SystemDoc) {
  try {
    selected.value = await docApi.get(d.key)
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

async function syncAll() {
  syncing.value = true
  try {
    const r = await docApi.sync()
    app.toast(`已同步 ${r.synced} 篇文档`)
    await loadList()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    syncing.value = false
  }
}

function startEdit() {
  if (!selected.value) return
  editContent.value = selected.value.content
  editTitle.value = selected.value.title
  editGroup.value = selected.value.group
  editing.value = true
}

async function saveEdit() {
  if (!selected.value) return
  if (!editTitle.value) {
    app.toast('文档命名不能为空', 'error')
    return
  }
  saving.value = true
  try {
    await docApi.update(selected.value.key, {
      title: editTitle.value,
      group: editGroup.value,
      content: editContent.value,
    })
    editing.value = false
    app.toast('已保存')
    await loadList()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    saving.value = false
  }
}

/* ---------------- 新建文档 ---------------- */
const createOpen = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = reactive({ title: '', group: '默认文档', key: '', content: '', fmt: 'markdown' })

function openCreate() {
  createError.value = ''
  Object.assign(createForm, {
    title: '',
    group: groupOptions.value[0] ?? '默认文档',
    key: '',
    content: '',
    fmt: 'markdown',
  })
  createOpen.value = true
}

async function submitCreate() {
  if (!createForm.title) {
    createError.value = '文档命名不能为空'
    return
  }
  creating.value = true
  try {
    const created = await docApi.create({
      title: createForm.title,
      group: createForm.group || '默认文档',
      key: createForm.key || undefined,
      content: createForm.content,
      fmt: createForm.fmt as 'markdown' | 'html',
    })
    createOpen.value = false
    app.toast('已创建文档')
    await loadList()
    if (created?.key) await select({ key: created.key } as SystemDoc)
  } catch (e) {
    createError.value = (e as Error).message
  } finally {
    creating.value = false
  }
}

onMounted(async () => {
  await loadGroups()
  await loadList()
})
</script>

<!-- 文档正文（v-html）排版：不作用于组件自身 scoped 之外的注入内容，故用全局样式 -->
<style>
.doc-prose {
  color: #1f2933;
  font-size: 15px;
  line-height: 1.8;
}
.doc-prose h1 { font-size: 24px; font-weight: 700; margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 1px solid #e6e8ec; }
.doc-prose h2 { font-size: 20px; font-weight: 700; margin: 22px 0 10px; }
.doc-prose h3 { font-size: 17px; font-weight: 600; margin: 18px 0 8px; color: #334155; }
.doc-prose h4 { font-size: 15px; font-weight: 600; margin: 14px 0 6px; color: #475569; }
.doc-prose p { margin: 10px 0; }
.doc-prose ul, .doc-prose ol { margin: 10px 0; padding-left: 22px; }
.doc-prose li { margin: 5px 0; }
.doc-prose a { color: #2563eb; text-decoration: underline; }
.doc-prose code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  background: #f1f5f9; border-radius: 5px; padding: 1px 6px; font-size: 13px; color: #0f172a;
}
.doc-prose pre {
  background: #0f172a; color: #e2e8f0; border-radius: 8px; padding: 12px 14px;
  overflow-x: auto; margin: 12px 0; font-size: 13px;
}
.doc-prose pre code { background: transparent; color: inherit; padding: 0; }
.doc-prose blockquote {
  border-left: 3px solid #2563eb; background: #eff4ff; padding: 8px 14px;
  border-radius: 0 8px 8px 0; margin: 12px 0; color: #475569;
}
.doc-prose table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 14px; }
.doc-prose th, .doc-prose td { border: 1px solid #e6e8ec; padding: 7px 10px; text-align: left; }
.doc-prose th { background: #f8fafc; color: #475569; font-weight: 600; }
.doc-prose hr { border: none; border-top: 1px solid #e6e8ec; margin: 18px 0; }
</style>
