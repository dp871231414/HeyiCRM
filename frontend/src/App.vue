<template>
  <div class="bg-blob bg-blob-1" />
  <div class="bg-blob bg-blob-2" />
  <router-view />
  <ToastHost />
</template>

<script setup lang="ts">
import ToastHost from '@/components/ToastHost.vue'
</script>
