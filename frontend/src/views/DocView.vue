<template>
  <div class="lg:flex lg:gap-4">
    <!-- 左：文档列表 -->
    <aside class="lg:w-60 lg:shrink-0 card p-3 mb-4 lg:mb-0">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-semibold text-slate-700">文档中心</h2>
        <button v-if="canEdit" class="btn-ghost btn-sm" :disabled="syncing" @click="syncAll">
          {{ syncing ? '同步中…' : '同步最新' }}
        </button>
      </div>
      <ul class="space-y-1">
        <li v-for="d in docs" :key="d.key">
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
      <p class="mt-3 text-[11px] text-slate-400 leading-snug">
        文档内容随系统迭代自动从源码同步至数据库；管理员可点「同步最新」刷新。
      </p>
    </aside>

    <!-- 右：内容 -->
    <section class="flex-1 card p-6 min-h-[60vh]">
      <div v-if="loading" class="text-slate-400 text-sm">加载中…</div>
      <div v-else-if="!selected" class="text-slate-400 text-sm">请选择左侧文档</div>
      <div v-else>
        <div class="mb-4 flex items-center gap-3 flex-wrap">
          <h1 class="text-xl font-bold text-slate-800">{{ selected.title }}</h1>
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

        <!-- 编辑态 -->
        <div v-if="editing">
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
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { docApi } from '@/api'
import type { SystemDoc } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'

const auth = useAuthStore()
const app = useAppStore()

const docs = ref<SystemDoc[]>([])
const selected = ref<SystemDoc | null>(null)
const loading = ref(false)
const syncing = ref(false)
const editing = ref(false)
const editContent = ref('')
const saving = ref(false)

const canEdit = computed(() => auth.hasPerm('sys.config.edit'))

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function loadList() {
  loading.value = true
  try {
    docs.value = await docApi.list()
    if (!selected.value && docs.value.length) {
      await select(docs.value[0])
    } else if (selected.value) {
      // 同步后刷新当前选中
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
  // 列表项不含完整 html，按需拉取
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
  editing.value = true
}

async function saveEdit() {
  if (!selected.value) return
  saving.value = true
  try {
    await docApi.update(selected.value.key, { content: editContent.value })
    editing.value = false
    app.toast('已保存')
    await loadList()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    saving.value = false
  }
}

onMounted(loadList)
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
