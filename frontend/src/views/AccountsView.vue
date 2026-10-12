<template>
  <div class="space-y-4">
    <!-- 页签 -->
    <div class="flex items-center gap-1.5 border-b border-slate-200">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition"
        :class="tab === t.key ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800'"
        @click="tab = t.key"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- ================= 账号 ================= -->
    <template v-if="tab === 'users'">
      <div class="card p-3.5 flex flex-wrap items-center gap-2.5">
        <input v-model.trim="userKeyword" class="input !w-56" placeholder="搜索姓名 / 账号" @keyup.enter="loadUsers" />
        <select v-model="userDept" class="input !w-44">
          <option value="">全部部门</option>
          <option v-for="o in orgs" :key="o.id" :value="o.id">{{ '　'.repeat(o.depth) }}{{ o.name }}</option>
        </select>
        <select v-model="userStatus" class="input !w-32">
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="disabled">停用</option>
        </select>
        <button class="btn-ghost" @click="loadUsers">查询</button>
        <button v-if="auth.hasPerm('account.edit')" class="btn-primary ml-auto" @click="openUserForm()">新增账号</button>
      </div>

      <div class="card overflow-x-auto">
        <div v-if="usersLoading" class="p-10 text-center text-slate-400 text-sm">加载中…</div>
        <div v-else-if="!users.length" class="p-10 text-center text-slate-400 text-sm">暂无账号</div>
        <table v-else class="w-full min-w-[1000px]">
          <thead>
            <tr class="border-b border-slate-200">
              <th class="th">姓名</th>
              <th class="th">账号</th>
              <th class="th">所属部门</th>
              <th class="th">角色</th>
              <th class="th">数据可见范围</th>
              <th class="th">状态</th>
              <th class="th">最近登录</th>
              <th class="th text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" class="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td class="td font-semibold text-slate-800">{{ u.name }}</td>
              <td class="td font-mono text-xs text-slate-500">{{ u.account }}</td>
              <td class="td">{{ u.deptName }}</td>
              <td class="td">{{ u.roleName }}</td>
              <td class="td">
                <span class="chip bg-slate-100 text-slate-600">{{ scopeLabel(u.effectiveScope) }}</span>
                <span v-if="u.scope" class="text-[11px] text-brand-600 ml-1">（账号覆盖）</span>
              </td>
              <td class="td">
                <span class="chip border" :class="u.status === 'active' ? 'bg-good-50 text-good-700 border-good-100' : 'bg-slate-100 text-slate-500 border-slate-200'">
                  {{ u.status === 'active' ? '启用' : '停用' }}
                </span>
              </td>
              <td class="td text-xs text-slate-500">
                {{ u.lastLoginAt || '—' }}
                <span v-if="u.lastLoginIp" class="text-slate-400"> · {{ u.lastLoginIp }}</span>
              </td>
              <td class="td text-right whitespace-nowrap">
                <template v-if="auth.hasPerm('account.edit')">
                  <button class="btn-ghost btn-sm" @click="openUserForm(u)">编辑</button>
                  <button class="btn-ghost btn-sm ml-1.5" @click="toggleStatus(u)">
                    {{ u.status === 'active' ? '停用' : '启用' }}
                  </button>
                </template>
                <span v-else class="text-xs text-slate-300">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ================= 组织结构 ================= -->
    <template v-else-if="tab === 'org'">
      <div class="card">
        <div class="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <h2 class="text-sm font-bold text-slate-900">组织结构</h2>
          <button v-if="auth.hasPerm('account.edit')" class="btn-primary btn-sm" @click="openOrgForm(null, 'CO')">
            创建二级部门
          </button>
        </div>
        <div v-if="orgLoading" class="p-10 text-center text-slate-400 text-sm">加载中…</div>
        <ul v-else class="divide-y divide-slate-100">
          <li
            v-for="o in orgs"
            :key="o.id"
            class="flex items-center gap-3 px-4 py-3 hover:bg-slate-50"
            :style="{ paddingLeft: `${16 + o.depth * 24}px` }"
          >
            <span class="w-2 h-2 rounded-full shrink-0" :class="o.type === 'company' ? 'bg-brand-600' : o.type === 'dept' ? 'bg-brand-300' : 'bg-slate-300'" />
            <span class="text-sm font-semibold text-slate-800">{{ o.name }}</span>
            <span class="text-[11px] text-slate-400">{{ o.id }}</span>
            <span class="text-xs text-slate-500">负责人 {{ o.head }}</span>
            <span class="text-[11px] text-slate-400">账号 {{ o.userCount }} · 任务 {{ o.taskCount }}</span>

            <div v-if="auth.hasPerm('account.edit')" class="ml-auto flex items-center gap-1.5">
              <button class="btn-ghost btn-sm" @click="openOrgForm(null, o.id)">+ 子部门</button>
              <button v-if="o.type !== 'company'" class="btn-ghost btn-sm" @click="openOrgForm(o)">编辑</button>
              <button
                v-if="o.type !== 'company'"
                class="btn-danger btn-sm"
                :disabled="o.userCount > 0 || o.childCount > 0"
                :title="deleteReason(o)"
                @click="askDeleteOrg(o)"
              >
                删除
              </button>
            </div>
          </li>
        </ul>
        <div class="px-4 py-3 border-t border-slate-200 text-xs text-slate-400">
          项目公司为独立核算单元，不在此维护；请到「指标维护」页新增 / 编辑 / 删除。
        </div>
      </div>
    </template>

    <!-- ================= 角色权限 ================= -->
    <template v-else>
      <div class="card p-3.5 flex flex-wrap items-center gap-2.5">
        <input v-model.trim="roleKeyword" class="input !w-56" placeholder="搜索角色名称" @keyup.enter="loadRoles" />
        <button class="btn-ghost" @click="loadRoles">查询</button>
        <button v-if="auth.hasPerm('account.role')" class="btn-primary ml-auto" @click="openRoleForm()">新增角色</button>
      </div>

      <div class="card overflow-x-auto">
        <div v-if="rolesLoading" class="p-10 text-center text-slate-400 text-sm">加载中…</div>
        <table v-else class="w-full min-w-[860px]">
          <thead>
            <tr class="border-b border-slate-200">
              <th class="th">角色名称</th>
              <th class="th">说明</th>
              <th class="th">数据可见范围</th>
              <th class="th">权限项</th>
              <th class="th w-24">关联账号</th>
              <th class="th text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in roles" :key="r.id" class="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td class="td">
                <span class="font-semibold text-slate-800">{{ r.name }}</span>
                <span v-if="r.isSystem" class="chip bg-brand-50 text-brand-700 border border-brand-100 ml-1.5">内置</span>
              </td>
              <td class="td text-slate-500 whitespace-normal max-w-[280px]">{{ r.description || '—' }}</td>
              <td class="td">{{ scopeLabel(r.scope) }}</td>
              <td class="td text-xs text-slate-500">{{ r.permissions.filter((p) => p.endsWith('.view')).length }} 个菜单 · {{ r.permissions.length }} 项权限</td>
              <td class="td">{{ r.userCount }}</td>
              <td class="td text-right whitespace-nowrap">
                <template v-if="auth.hasPerm('account.role')">
                  <button class="btn-ghost btn-sm" @click="openRoleForm(r)">编辑</button>
                  <button
                    class="btn-danger btn-sm ml-1.5"
                    :disabled="r.isSystem || r.userCount > 0"
                    :title="r.isSystem ? '内置角色不可删除' : r.userCount > 0 ? '该角色下仍有账号' : ''"
                    @click="askDeleteRole(r)"
                  >
                    删除
                  </button>
                </template>
                <span v-else class="text-xs text-slate-300">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 账号表单 -->
    <ModalDialog :open="userFormOpen" :title="userForm.id ? '编辑账号' : '新增账号'" @close="userFormOpen = false">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="label">姓名</label>
          <input v-model.trim="userForm.name" class="input" />
        </div>
        <div>
          <label class="label">账号</label>
          <input v-model.trim="userForm.account" class="input" :disabled="!!userForm.id" />
        </div>
        <div>
          <label class="label">{{ userForm.id ? '重置密码（留空不改）' : '初始密码' }}</label>
          <input v-model="userForm.password" type="password" class="input" autocomplete="new-password" />
        </div>
        <div>
          <label class="label">状态</label>
          <select v-model="userForm.status" class="input">
            <option value="active">启用</option>
            <option value="disabled">停用</option>
          </select>
        </div>
        <div>
          <label class="label">所属部门</label>
          <select v-model="userForm.deptId" class="input">
            <option v-for="o in orgs" :key="o.id" :value="o.id">{{ '　'.repeat(o.depth) }}{{ o.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">角色</label>
          <select v-model="userForm.roleId" class="input">
            <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
        </div>
        <div class="md:col-span-2">
          <label class="label">数据可见范围</label>
          <select v-model="userForm.scope" class="input">
            <option value="">跟随角色默认（{{ scopeLabel(roleDefaultScope) }}）</option>
            <option v-for="s in scopes" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </div>
      </div>
      <p v-if="userError" class="mt-3 text-sm text-bad-600">{{ userError }}</p>
      <template #footer>
        <button class="btn-ghost" @click="userFormOpen = false">取消</button>
        <button class="btn-primary" :disabled="saving === 'user'" @click="saveUser">保存</button>
      </template>
    </ModalDialog>

    <!-- 部门表单 -->
    <ModalDialog :open="orgFormOpen" :title="orgForm.id ? '编辑部门' : '新增部门'" width="sm" @close="orgFormOpen = false">
      <div class="space-y-4">
        <div>
          <label class="label">部门名称</label>
          <input v-model.trim="orgForm.name" class="input" />
        </div>
        <div>
          <label class="label">负责人</label>
          <input v-model.trim="orgForm.head" class="input" placeholder="可留空" />
        </div>
        <p v-if="!orgForm.id" class="text-xs text-slate-400">
          上级组织：{{ parentName }}
        </p>
        <p v-if="orgError" class="text-sm text-bad-600">{{ orgError }}</p>
      </div>
      <template #footer>
        <button class="btn-ghost" @click="orgFormOpen = false">取消</button>
        <button class="btn-primary" @click="saveOrg">保存</button>
      </template>
    </ModalDialog>

    <!-- 角色表单 -->
    <ModalDialog :open="roleFormOpen" :title="roleForm.id ? '编辑角色' : '新增角色'" width="lg" @close="roleFormOpen = false">
      <div class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="label">角色名称</label>
            <input v-model.trim="roleForm.name" class="input" />
          </div>
          <div>
            <label class="label">数据可见范围</label>
            <select v-model="roleForm.scope" class="input">
              <option v-for="s in scopes" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </div>
          <div class="md:col-span-2">
            <label class="label">说明</label>
            <input v-model.trim="roleForm.description" class="input" />
          </div>
          <div class="md:col-span-2">
            <label class="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" v-model="roleForm.isSystem" class="w-4 h-4 accent-brand-600" />
              <span class="text-xs text-slate-600">
                标记为内置角色
                <span class="text-slate-400">（内置角色受删除保护；可按需取消，取消后该角色即可被删除）</span>
              </span>
            </label>
          </div>
        </div>

        <div>
          <label class="label">权限配置</label>
          <div class="border border-slate-200 rounded-lg divide-y divide-slate-100">
            <div v-for="g in catalog?.groups ?? []" :key="g.menu" class="px-3.5 py-3">
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  class="w-4 h-4 accent-brand-600"
                  :checked="isMenuChecked(g.menu)"
                  @change="toggleMenu(g.menu, ($event.target as HTMLInputElement).checked)"
                />
                <span class="text-sm font-semibold text-slate-800">{{ g.label }}</span>
                <span class="text-[11px] text-slate-400">菜单权限</span>
              </label>
              <!-- 动作权限按子分组展示，让「这个权限管页面哪一块」一眼可见 -->
              <div v-for="sec in actionSections(g)" :key="sec.name" class="mt-2 ml-6">
                <div v-if="sec.name" class="mb-1.5 text-[11px] font-semibold text-slate-400">
                  {{ sec.name }}
                </div>
                <div class="flex flex-wrap gap-x-5 gap-y-2">
                  <label v-for="item in sec.items" :key="item.key" class="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      class="w-4 h-4 accent-brand-600"
                      :checked="roleForm.permissions.includes(item.key)"
                      :disabled="!isMenuChecked(g.menu)"
                      @change="togglePerm(item.key, ($event.target as HTMLInputElement).checked)"
                    />
                    <span class="text-xs text-slate-600">{{ item.label }}</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>
        <p v-if="roleError" class="text-sm text-bad-600">{{ roleError }}</p>
      </div>
      <template #footer>
        <button class="btn-ghost" @click="roleFormOpen = false">取消</button>
        <button class="btn-primary" :disabled="saving === 'role'" @click="saveRole">保存</button>
      </template>
    </ModalDialog>

    <!-- 删除确认 -->
    <ModalDialog :open="!!deleteMsg" title="确认删除" width="sm" @close="deleteMsg = ''">
      <p class="text-sm text-slate-600">{{ deleteMsg }}</p>
      <template #footer>
        <button class="btn-ghost" @click="deleteMsg = ''">取消</button>
        <button class="btn-danger" @click="confirmDeleteAction">确认删除</button>
      </template>
    </ModalDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { orgApi, roleApi, userApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { OrgNode, PermCatalog, PermGroup, PermItem, RoleItem, ScopeKey, UserItem } from '@/types'

const auth = useAuthStore()
const app = useAppStore()

const tabs: { key: 'users' | 'org' | 'roles'; label: string }[] = [
  { key: 'users', label: '账号' },
  { key: 'org', label: '组织结构' },
  { key: 'roles', label: '角色权限' },
]
const tab = ref<'users' | 'org' | 'roles'>('users')

const orgs = ref<OrgNode[]>([])
const roles = ref<RoleItem[]>([])
const users = ref<UserItem[]>([])
const catalog = ref<PermCatalog | null>(null)
const scopes = computed(() => catalog.value?.scopes ?? [])

/**
 * 把某个菜单下的动作权限按子分组归类，供角色表单分块展示。
 * 保持原顺序；没有 group 的项归入一个无名分组，显示在其首次出现的位置。
 */
function actionSections(g: PermGroup): { name: string; items: PermItem[] }[] {
  const out: { name: string; items: PermItem[] }[] = []
  const index = new Map<string, number>()
  for (const item of g.items) {
    if (item.type !== 'action') continue
    const name = item.group ?? ''
    let i = index.get(name)
    if (i === undefined) {
      i = out.length
      index.set(name, i)
      out.push({ name, items: [] })
    }
    out[i].items.push(item)
  }
  return out
}

const orgLoading = ref(false)
const usersLoading = ref(false)
const rolesLoading = ref(false)
const saving = ref('')

const userKeyword = ref('')
const userDept = ref('')
const userStatus = ref('')
const roleKeyword = ref('')

const userFormOpen = ref(false)
const userError = ref('')
const userForm = reactive({ id: '', name: '', account: '', password: '', deptId: 'CO', roleId: 'member', scope: '', status: 'active' })

const orgFormOpen = ref(false)
const orgError = ref('')
const orgForm = reactive({ id: '', name: '', head: '', parentId: 'CO' })

const roleFormOpen = ref(false)
const roleError = ref('')
const roleForm = reactive<{ id: string; name: string; description: string; scope: ScopeKey; permissions: string[]; isSystem: boolean }>({ id: '', name: '', description: '', scope: 'self', permissions: [], isSystem: false })

const deleteMsg = ref('')
let deleteAction: (() => Promise<void>) | null = null

const SCOPE_TEXT: Record<string, string> = {
  self: '本人',
  dept: '本部门',
  dept_sub: '本部门及下属部门',
  all: '全公司',
}
const scopeLabel = (s: string) => SCOPE_TEXT[s] ?? s
const parentName = computed(() => orgs.value.find((o) => o.id === orgForm.parentId)?.name ?? orgForm.parentId)
const roleDefaultScope = computed(() => roles.value.find((r) => r.id === userForm.roleId)?.scope ?? 'self')

function deleteReason(o: OrgNode) {
  if (o.userCount > 0) return `该部门下有 ${o.userCount} 个账号，不允许删除，仅可修改`
  if (o.childCount > 0) return `该部门下有 ${o.childCount} 个下级部门，请先删除下级部门`
  return '删除该部门（其下任务将上移到上级部门）'
}

/* ---------------- 加载 ---------------- */
async function loadOrgs() {
  orgLoading.value = true
  try {
    orgs.value = await orgApi.list()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    orgLoading.value = false
  }
}

async function loadRoles() {
  rolesLoading.value = true
  try {
    roles.value = await roleApi.list(roleKeyword.value)
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    rolesLoading.value = false
  }
}

async function loadUsers() {
  usersLoading.value = true
  try {
    users.value = await userApi.list({ keyword: userKeyword.value, dept_id: userDept.value, status: userStatus.value })
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    usersLoading.value = false
  }
}

async function loadCatalog() {
  if (!auth.hasPerm('account.view')) return
  try {
    catalog.value = await roleApi.catalog()
  } catch {
    /* 忽略 */
  }
}

/* ---------------- 账号 ---------------- */
function openUserForm(u?: UserItem) {
  userError.value = ''
  if (u) {
    Object.assign(userForm, {
      id: u.id,
      name: u.name,
      account: u.account,
      password: '',
      deptId: u.deptId,
      roleId: u.roleId,
      scope: u.scope ?? '',
      status: u.status,
    })
  } else {
    Object.assign(userForm, {
      id: '',
      name: '',
      account: '',
      password: '',
      deptId: orgs.value[1]?.id ?? 'CO',
      roleId: roles.value.find((r) => !r.isSystem)?.id ?? roles.value[0]?.id ?? 'member',
      scope: '',
      status: 'active',
    })
  }
  userFormOpen.value = true
}

async function saveUser() {
  userError.value = ''
  if (!userForm.name || !userForm.account) {
    userError.value = '姓名与账号不能为空'
    return
  }
  if (!userForm.id && userForm.password.length < 6) {
    userError.value = '初始密码至少 6 位'
    return
  }
  saving.value = 'user'
  try {
    const payload: Record<string, unknown> = {
      name: userForm.name,
      dept_id: userForm.deptId,
      role_id: userForm.roleId,
      scope: userForm.scope,
      status: userForm.status,
    }
    if (userForm.id) {
      if (userForm.password) payload.password = userForm.password
      await userApi.update(userForm.id, payload)
    } else {
      payload.account = userForm.account
      payload.password = userForm.password
      await userApi.create(payload)
    }
    app.toast('已保存')
    userFormOpen.value = false
    await loadUsers()
  } catch (e) {
    userError.value = (e as Error).message
  } finally {
    saving.value = ''
  }
}

async function toggleStatus(u: UserItem) {
  try {
    await userApi.setStatus(u.id, u.status === 'active' ? 'disabled' : 'active')
    app.toast('已更新账号状态')
    await loadUsers()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

/* ---------------- 组织 ---------------- */
function openOrgForm(o: OrgNode | null, parentId = 'CO') {
  orgError.value = ''
  orgForm.id = o?.id ?? ''
  orgForm.name = o?.name ?? ''
  orgForm.head = o?.head ?? ''
  orgForm.parentId = o?.parentId ?? parentId
  orgFormOpen.value = true
}

async function saveOrg() {
  orgError.value = ''
  if (!orgForm.name) {
    orgError.value = '部门名称不能为空'
    return
  }
  saving.value = 'org'
  try {
    if (orgForm.id) await orgApi.update(orgForm.id, { name: orgForm.name, head: orgForm.head })
    else await orgApi.create({ name: orgForm.name, parent_id: orgForm.parentId, head: orgForm.head })
    app.toast('已保存')
    orgFormOpen.value = false
    await loadOrgs()
  } catch (e) {
    orgError.value = (e as Error).message
  } finally {
    saving.value = ''
  }
}

function askDeleteOrg(o: OrgNode) {
  deleteMsg.value = `将删除部门「${o.name}」。该部门下的任务会上移到其上级部门。`
  deleteAction = async () => {
    await orgApi.remove(o.id)
    app.toast('已删除')
    await loadOrgs()
  }
}

/* ---------------- 角色 ---------------- */
function openRoleForm(r?: RoleItem) {
  roleError.value = ''
  if (r) {
    Object.assign(roleForm, { id: r.id, name: r.name, description: r.description, scope: r.scope, permissions: [...r.permissions], isSystem: !!r.isSystem })
  } else {
    Object.assign(roleForm, { id: '', name: '', description: '', scope: 'self', permissions: ['dashboard.view'], isSystem: false })
  }
  roleFormOpen.value = true
}

function isMenuChecked(menu: string) {
  const g = catalog.value?.groups.find((x) => x.menu === menu)
  const menuKey = g?.items.find((i) => i.type === 'menu')?.key
  return !!menuKey && roleForm.permissions.includes(menuKey)
}

function toggleMenu(menu: string, checked: boolean) {
  const g = catalog.value?.groups.find((x) => x.menu === menu)
  if (!g) return
  const keys = g.items.map((i) => i.key)
  if (checked) {
    roleForm.permissions = Array.from(new Set([...roleForm.permissions, ...keys.slice(0, 1)]))
  } else {
    roleForm.permissions = roleForm.permissions.filter((p) => !keys.includes(p))
  }
}

function togglePerm(key: string, checked: boolean) {
  if (checked) roleForm.permissions = Array.from(new Set([...roleForm.permissions, key]))
  else roleForm.permissions = roleForm.permissions.filter((p) => p !== key)
}

async function saveRole() {
  roleError.value = ''
  if (!roleForm.name) {
    roleError.value = '角色名称不能为空'
    return
  }
  saving.value = 'role'
  try {
    const payload = { name: roleForm.name, description: roleForm.description, scope: roleForm.scope, permissions: roleForm.permissions, isSystem: roleForm.isSystem }
    if (roleForm.id) await roleApi.update(roleForm.id, payload)
    else await roleApi.create(payload)
    app.toast('已保存')
    roleFormOpen.value = false
    await loadRoles()
  } catch (e) {
    roleError.value = (e as Error).message
  } finally {
    saving.value = ''
  }
}

function askDeleteRole(r: RoleItem) {
  deleteMsg.value = `将删除角色「${r.name}」。`
  deleteAction = async () => {
    await roleApi.remove(r.id)
    app.toast('已删除')
    await loadRoles()
  }
}

async function confirmDeleteAction() {
  try {
    await deleteAction?.()
    deleteMsg.value = ''
  } catch (e) {
    app.toast((e as Error).message, 'error')
    deleteMsg.value = ''
  }
}

onMounted(async () => {
  await loadCatalog()
  await Promise.all([loadOrgs(), loadRoles(), loadUsers()])
})
</script>
