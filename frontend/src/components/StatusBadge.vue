<template>
  <span class="chip border" :class="cls">
    <span v-if="dot" class="w-1.5 h-1.5 rounded-full" :class="dotClass" />
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { LIGHT_CLASS, LIGHT_DOT, LIGHT_LABEL, STATUS_CLASS } from '@/utils/format'
import type { Light } from '@/types'

const props = withDefaults(
  defineProps<{ light?: Light; status?: string; text?: string; dot?: boolean }>(),
  { light: undefined, status: undefined, text: undefined, dot: false },
)

const cls = computed(() => (props.status ? STATUS_CLASS[props.status] ?? LIGHT_CLASS.none : LIGHT_CLASS[props.light ?? 'none']))
const dotClass = computed(() => LIGHT_DOT[props.light ?? 'none'])
const label = computed(() => props.text ?? (props.light ? LIGHT_LABEL[props.light] : ''))
</script>
