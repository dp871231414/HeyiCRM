<template>
  <div class="min-h-screen grid lg:grid-cols-2 relative z-10">
    <!-- 品牌视觉区 -->
    <section class="login-visual hidden lg:flex flex-col justify-center px-14 text-white">
      <div class="lv-deco lv-grid" />
      <div class="lv-deco lv-glow" />
      <div class="lv-deco lv-orbit" />
      <div class="lv-deco lv-ring" />

      <div class="relative z-10">
        <div class="flex items-center gap-3.5 mb-8">
          <div
            class="w-12 h-12 rounded-xl bg-white/15 border border-white/25 backdrop-blur grid place-items-center text-xl font-extrabold"
          >
            合
          </div>
          <div class="text-sm font-semibold tracking-wide text-white/80">合一绿能 · 数字化经营</div>
        </div>

        <h1 class="text-[40px] leading-[1.15] font-extrabold tracking-tight">合一重卡生态经营看板</h1>
        <p class="mt-4 text-[15px] leading-relaxed text-white/80 max-w-[620px]">
          目标下达 · 数据填报 · 达成判定 · 风险提示 —— 让经营数据一次填报、全员同源、责任可追溯。
        </p>

        <div class="mt-12 grid grid-cols-3 gap-4 max-w-[520px]">
          <div v-for="item in highlights" :key="item.t" class="rounded-xl bg-white/10 border border-white/15 px-3.5 py-3">
            <div class="text-[13px] font-bold">{{ item.t }}</div>
            <div class="text-[11px] text-white/70 mt-1">{{ item.d }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 表单区 -->
    <section class="flex items-center justify-center px-6 py-12 bg-white">
      <div class="w-full max-w-[380px]">
        <div class="lg:hidden flex items-center gap-3 mb-8">
          <div
            class="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-600 to-violetx-600 text-white grid place-items-center font-extrabold"
          >
            合
          </div>
          <div class="text-lg font-extrabold text-slate-900">合一重卡生态经营看板</div>
        </div>

        <h2 class="text-2xl font-extrabold text-slate-900">账号登录</h2>
        <p class="text-sm text-slate-500 mt-1.5">请使用系统分配的账号登录经营看板</p>

        <form class="mt-8 space-y-4" @submit.prevent="submit">
          <div>
            <label class="label" for="account">账号</label>
            <input id="account" v-model.trim="account" class="input" placeholder="请输入账号" autocomplete="username" />
          </div>
          <div>
            <label class="label" for="password">密码</label>
            <input
              id="password"
              v-model="password"
              type="password"
              class="input"
              placeholder="请输入密码"
              autocomplete="current-password"
            />
          </div>

          <p v-if="error" class="text-sm text-bad-600 bg-bad-50 border border-bad-100 rounded-lg px-3 py-2">
            {{ error }}
          </p>

          <button type="submit" class="btn-primary w-full !py-2.5" :disabled="loading || !account || !password">
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </form>

        <p class="mt-6 text-xs text-slate-400 leading-relaxed">
          演示账号由管理员初始化。若忘记密码或账号被停用，请联系系统管理员。
        </p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const app = useAppStore()
const route = useRoute()
const router = useRouter()

const account = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const highlights = [
  { t: '统一口径', d: '指标定义唯一来源' },
  { t: '自动判定', d: '红黄绿灯与风险规则生成' },
  { t: '分权可见', d: '按组织与角色隔离数据' },
]

onMounted(() => {
  if (route.query.reason === 'expired') error.value = '登录已过期，请重新登录'
})

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(account.value, password.value)
    app.toast(`欢迎回来，${auth.user?.name}`)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
</script>
