<template>
  <transition name="fade">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/45" @click="closeOnMask && emit('close')" />
      <div
        class="relative bg-white rounded-xl2 shadow-pop w-full max-h-[88vh] overflow-hidden flex flex-col"
        :class="widthClass"
      >
        <header class="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <h3 class="text-base font-bold text-slate-900">{{ title }}</h3>
          <button class="text-slate-400 hover:text-slate-700 text-xl leading-none" @click="emit('close')">×</button>
        </header>
        <div class="px-5 py-4 overflow-y-auto flex-1">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="px-5 py-3.5 border-t border-slate-200 bg-slate-50 flex justify-end gap-2">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ open: boolean; title: string; width?: 'sm' | 'md' | 'lg' | 'xl'; closeOnMask?: boolean }>(),
  { width: 'md', closeOnMask: true },
)
const emit = defineEmits<{ close: [] }>()

const widthClass = computed(
  () => ({ sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' })[props.width],
)
</script>
