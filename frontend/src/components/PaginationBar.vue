<template>
  <div class="inline-flex items-center gap-2 text-xs">
    <button class="btn-ghost btn-sm" :disabled="page <= 1" @click="emit('update:page', page - 1)">
      上一页
    </button>
    <span class="tabular-nums text-slate-500">
      第 <b class="text-slate-800">{{ page }}</b> / {{ pageCount }} 页
      <span v-if="total > 0" class="text-slate-400">· 共 {{ total }} 项</span>
    </span>
    <button class="btn-ghost btn-sm" :disabled="page >= pageCount" @click="emit('update:page', page + 1)">
      下一页
    </button>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    page: number
    pageCount: number
    total?: number
  }>(),
  { total: 0 },
)

const emit = defineEmits<{ 'update:page': [number] }>()
</script>
