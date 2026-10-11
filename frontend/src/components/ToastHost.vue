<template>
  <div data-testid="toast-host" class="fixed top-4 right-4 z-[100] space-y-2 w-80">
    <transition-group name="fade">
      <div
        v-for="t in app.toasts"
        :key="t.id"
        class="flex items-start gap-2 rounded-xl border px-3.5 py-3 shadow-pop text-sm font-medium"
        :class="classes(t.type)"
      >
        <span class="mt-0.5">{{ icon(t.type) }}</span>
        <span class="flex-1">{{ t.text }}</span>
      </div>
    </transition-group>
  </div>
</template>

<script setup lang="ts">
import { useAppStore, type ToastItem } from '@/stores/app'

const app = useAppStore()

function classes(type: ToastItem['type']) {
  if (type === 'error') return 'bg-bad-50 border-bad-100 text-bad-700'
  if (type === 'info') return 'bg-brand-50 border-brand-100 text-brand-700'
  return 'bg-good-50 border-good-100 text-good-700'
}

function icon(type: ToastItem['type']) {
  if (type === 'error') return '✕'
  if (type === 'info') return 'ℹ'
  return '✓'
}
</script>
