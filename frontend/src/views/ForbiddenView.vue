<template>
  <div class="card max-w-lg mx-auto mt-20 p-10 text-center">
    <div class="w-14 h-14 rounded-2xl bg-bad-50 text-bad-600 grid place-items-center text-2xl mx-auto mb-4">!</div>
    <h2 class="text-lg font-bold text-slate-900">无访问权限</h2>
    <p class="text-sm text-slate-500 mt-2">
      当前角色没有该页面的访问权限。如需开通，请联系系统管理员调整你的角色菜单权限。
    </p>
    <div class="mt-6 flex justify-center gap-2">
      <router-link class="btn-primary" to="/dashboard">返回经营驾驶舱</router-link>
    </div>
  </div>
</template>
