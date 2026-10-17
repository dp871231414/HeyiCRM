<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-extrabold tracking-display text-slate-900">下载中心</h2>
        <p class="text-xs text-slate-400 mt-0.5">
          所有导出都会先在这里生成一条记录，可随时重新下载或删除（仅本人可见本人创建的记录）。
        </p>
      </div>
      <button class="btn-ghost btn-sm" @click="load" :disabled="loading">刷新</button>
    </div>

    <div class="card overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-slate-500 bg-slate-50">
            <th class="px-4 py-2.5 font-semibold">记录ID</th>
            <th class="px-4 py-2.5 font-semibold">导出文件名称</th>
            <th class="px-4 py-2.5 font-semibold">对象</th>
            <th class="px-4 py-2.5 font-semibold">创建人</th>
            <th class="px-4 py-2.5 font-semibold">创建时间</th>
            <th class="px-4 py-2.5 font-semibold text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!loading && !records.length" class="border-t border-slate-100">
            <td colspan="6" class="px-4 py-10 text-center text-slate-400">暂无导出记录</td>
          </tr>
          <tr
            v-for="r in records"
            :key="r.id"
            class="border-t border-slate-100 hover:bg-slate-50/60"
          >
            <td class="px-4 py-2.5 tabular-nums text-slate-500">{{ r.id }}</td>
            <td class="px-4 py-2.5 font-medium text-slate-800">{{ r.filename }}</td>
            <td class="px-4 py-2.5">
              <span class="badge-soft">{{ objectLabel(r.objectType) }}</span>
            </td>
            <td class="px-4 py-2.5 text-slate-600">{{ r.createdByName }}</td>
            <td class="px-4 py-2.5 tabular-nums text-slate-500">{{ r.createdAt }}</td>
            <td class="px-4 py-2.5 text-right whitespace-nowrap">
              <button class="btn-link mr-3" @click="onDownload(r)">下载</button>
              <button class="btn-link-danger" @click="onDelete(r)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="loading" class="px-4 py-10 text-center text-slate-400">加载中…</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { downloadApi, downloadFile } from '@/api'
import type { DownloadRecord } from '@/types'
import { useAppStore } from '@/stores/app'

const app = useAppStore()
const records = ref<DownloadRecord[]>([])
const loading = ref(false)

const OBJECT_LABELS: Record<string, string> = {
  task: '重点任务',
  market_project: '市场项目',
}
function objectLabel(t: string) {
  return OBJECT_LABELS[t] || t
}

async function load() {
  loading.value = true
  try {
    records.value = await downloadApi.list()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    loading.value = false
  }
}

async function onDownload(r: DownloadRecord) {
  try {
    await downloadFile(downloadApi.fileUrl(r.id), r.filename)
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

async function onDelete(r: DownloadRecord) {
  if (!confirm(`确定删除导出记录「${r.filename}」？文件将一并移除。`)) return
  try {
    await downloadApi.remove(r.id)
    app.toast('已删除')
    await load()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

onMounted(load)
</script>
