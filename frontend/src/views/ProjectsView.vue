<template>
  <div class="space-y-4">
    <!-- 工具条 -->
    <div class="card p-3.5 flex flex-wrap items-center gap-2.5">
      <input v-model.trim="keyword" class="input !w-56" placeholder="搜索项目ID / 名称 / 责任人" @keyup.enter="applyFilters" />
      <select v-model="stageFilter" class="input !w-44" @change="applyFilters">
        <option value="">全部阶段</option>
        <option v-for="s in STAGES" :key="s" :value="s">{{ s }}% {{ MARKET_STAGE_LABELS[s] }}</option>
      </select>
      <button class="btn-ghost" @click="applyFilters">查询</button>

      <div class="ml-auto flex items-center gap-2">
        <!-- 行高设置：按账号记忆，下次登录仍生效 -->
        <div class="flex items-center gap-1.5">
          <span class="text-xs text-slate-400">行高</span>
          <select v-model="rowHeightSel" class="input !w-32" @change="onRowHeightChange">
            <option value="default">默认</option>
            <option value="high">高（2X）</option>
            <option value="ultra">超高（3X）</option>
          </select>
        </div>
        <button class="btn-ghost" @click="onExportMarket">导出</button>
        <button v-if="auth.hasPerm('market.import')" class="btn-ghost" @click="importOpen = true">批量导入</button>
        <button v-if="auth.hasPerm('market.edit')" class="btn-primary" @click="openForm()">新建项目</button>
      </div>
    </div>

    <!-- 汇总 -->
    <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500 px-1">
      <span>共 <b class="text-slate-800">{{ total }}</b> 个项目</span>
      <span>车头数量 <b class="text-brand-600">{{ sumOf('tractorDemand') }}</b> 辆</span>
      <span>挂车数量 <b class="text-brand-600">{{ sumOf('trailerDemand') }}</b> 辆</span>
    </div>

    <!-- 表格 -->
    <div class="card overflow-hidden">
      <div v-if="loading" class="p-10 text-center text-slate-400 text-sm">加载中…</div>
      <div v-else-if="!projects.length" class="p-10 text-center text-slate-400 text-sm">暂无项目</div>
      <div v-else class="overflow-x-auto">
        <table :class="rowHeightClass" class="table-freeze table-fixed w-[1716px]">
          <thead>
            <tr class="border-b border-slate-200">
              <th class="th col-id w-[96px]">项目ID</th>
              <th class="th col-pname w-[213px]">项目名称</th>
              <th class="th w-[307px]">项目进展</th>
              <th class="th w-[150px]">项目阶段</th>
              <th class="th w-[110px] text-right">车头数量</th>
              <th class="th w-[100px] text-right">挂车数量</th>
              <th class="th w-[90px]">责任人</th>
              <th class="th w-[120px]">所属部门</th>
              <th class="th w-[90px]">创建人</th>
              <th class="th w-[140px]">创建时间</th>
              <th class="th w-[140px]">更新时间</th>
              <th class="th col-ops w-[160px] text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in projects" :key="p.id" class="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td class="td col-id font-mono text-xs text-slate-500">{{ p.id }}</td>
              <td class="td col-pname w-[213px]">
                <div class="cell-c font-semibold text-slate-800" :title="p.name">{{ p.name }}</div>
              </td>
              <td class="td w-[307px]">
                <div class="cell-c text-slate-600" :title="p.latestProgress || '—'">{{ p.latestProgress || '—' }}</div>
              </td>
              <td class="td">
                <span class="chip border" :class="STAGE_CHIP[p.stage]">{{ p.stage }}% {{ p.stageLabel }}</span>
              </td>
              <td class="td text-right font-mono">{{ p.tractorDemand }}<span class="text-[11px] text-slate-400 ml-0.5">辆</span></td>
              <td class="td text-right font-mono">{{ p.trailerDemand }}<span class="text-[11px] text-slate-400 ml-0.5">辆</span></td>
              <td class="td">{{ p.owner }}</td>
              <td class="td text-slate-500">{{ p.ownerDeptName || '—' }}</td>
              <td class="td text-slate-500">{{ p.createdByName || '—' }}</td>
              <td class="td text-xs text-slate-500">{{ fmtTime(p.createdAt) }}</td>
              <td class="td text-xs text-slate-500">{{ fmtTime(p.updatedAt) }}</td>
              <td class="td col-ops text-right whitespace-nowrap">
                <button v-if="auth.hasPerm('market.detail')" class="btn-ghost btn-sm" @click="openDetail(p)">详情</button>
                <button v-if="auth.hasPerm('market.edit')" class="btn-ghost btn-sm ml-1.5" @click="openForm(p)">编辑</button>
                <button
                  v-if="auth.hasPerm('market.delete')"
                  class="btn-danger btn-sm ml-1.5"
                  @click="deleteTarget = p"
                >
                  删除
                </button>
                <span v-if="!auth.hasAnyPerm(['market.detail', 'market.edit', 'market.delete'])" class="text-xs text-slate-300">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- 分页器：始终显示（与任务管理一致） -->
      <div class="flex items-center justify-between border-t border-slate-100 px-3.5 py-2.5">
        <span class="text-xs text-slate-400">每页最多 {{ PAGE_SIZE }} 条</span>
        <PaginationBar :page="page" :page-count="pageCount" :total="total" @update:page="goPage" />
      </div>
    </div>

    <!-- 新建 / 编辑 -->
    <ModalDialog :open="formOpen" :title="form.id ? '编辑项目' : '新建项目'" width="lg" @close="formOpen = false">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="md:col-span-2">
          <label class="label">项目名称<span class="req">*</span></label>
          <input v-model.trim="form.name" class="input" placeholder="如：华东物流园运力替换项目" />
        </div>
        <div>
          <label class="label">项目阶段<span class="req">*</span></label>
          <select v-model.number="form.stage" class="input">
            <option v-for="s in STAGES" :key="s" :value="s">{{ s }}% {{ MARKET_STAGE_LABELS[s] }}</option>
          </select>
        </div>
        <div>
          <label class="label">责任人<span class="req">*</span></label>
          <select v-model="form.owner" class="input" @change="onOwnerChange">
            <option value="" disabled>请选择责任人</option>
            <option v-for="o in marketOwners" :key="o.id" :value="o.name">{{ o.name }}（{{ o.deptName }}）</option>
          </select>
        </div>
        <div>
          <label class="label">所属部门<span class="text-slate-400 font-normal">（选责任人后自动带出）</span></label>
          <input :value="form.ownerDeptName" class="input bg-slate-50" disabled placeholder="选择责任人后自动带出" />
        </div>

        <!-- 车头需求：子列表（车辆型号 / 电池度数 / 数量），列头展示字段名，下方为可增删的表格 -->
        <div class="md:col-span-2">
          <div class="flex items-center justify-between mb-2">
            <label class="label !mb-0">车头需求<span class="text-slate-400 font-normal">（车辆型号取自数据字典）</span></label>
            <button class="btn-ghost btn-sm" @click="form.tractorRequirements.push({ model: '', battery: '', qty: 0 })">+ 添加一行</button>
          </div>
          <div v-if="!form.tractorRequirements.length" class="text-xs text-slate-400 py-2 text-center border border-dashed border-slate-200 rounded-lg">
            暂无车头需求，点击「添加一行」录入
          </div>
          <table v-else class="w-full text-sm border-collapse">
            <thead>
              <tr class="text-left text-slate-500 bg-slate-50">
                <th class="py-1.5 px-2 font-medium border border-slate-200">车辆型号</th>
                <th class="py-1.5 px-2 font-medium border border-slate-200">电池度数</th>
                <th class="py-1.5 px-2 font-medium border border-slate-200 w-24">数量</th>
                <th class="py-1.5 px-2 font-medium border border-slate-200 w-16 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in form.tractorRequirements" :key="i">
                <td class="py-1 px-2 border border-slate-200">
                  <select v-model="row.model" class="input w-full" :class="row.model ? '' : 'text-slate-400'">
                    <option value="">请选择</option>
                    <option v-for="m in vehicleModels" :key="m" :value="m">{{ m }}</option>
                  </select>
                </td>
                <td class="py-1 px-2 border border-slate-200">
                  <input v-model.trim="row.battery" class="input w-full" placeholder="电池度数" />
                </td>
                <td class="py-1 px-2 border border-slate-200">
                  <input v-model.number="row.qty" type="number" min="0" class="input w-full" placeholder="数量" />
                </td>
                <td class="py-1 px-2 border border-slate-200 text-center">
                  <button class="btn-ghost btn-sm" @click="form.tractorRequirements.splice(i, 1)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 挂车需求：子列表（挂车型号 / 电池度数 / 数量），列头展示字段名，下方为可增删的表格 -->
        <div class="md:col-span-2">
          <div class="flex items-center justify-between mb-2">
            <label class="label !mb-0">挂车需求<span class="text-slate-400 font-normal">（挂车型号取自数据字典）</span></label>
            <button class="btn-ghost btn-sm" @click="form.trailerRequirements.push({ model: '', battery: '', qty: 0 })">+ 添加一行</button>
          </div>
          <div v-if="!form.trailerRequirements.length" class="text-xs text-slate-400 py-2 text-center border border-dashed border-slate-200 rounded-lg">
            暂无挂车需求，点击「添加一行」录入
          </div>
          <table v-else class="w-full text-sm border-collapse">
            <thead>
              <tr class="text-left text-slate-500 bg-slate-50">
                <th class="py-1.5 px-2 font-medium border border-slate-200">挂车型号</th>
                <th class="py-1.5 px-2 font-medium border border-slate-200">电池度数</th>
                <th class="py-1.5 px-2 font-medium border border-slate-200 w-24">数量</th>
                <th class="py-1.5 px-2 font-medium border border-slate-200 w-16 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in form.trailerRequirements" :key="i">
                <td class="py-1 px-2 border border-slate-200">
                  <select v-model="row.model" class="input w-full" :class="row.model ? '' : 'text-slate-400'">
                    <option value="">请选择</option>
                    <option v-for="m in trailerModels" :key="m" :value="m">{{ m }}</option>
                  </select>
                </td>
                <td class="py-1 px-2 border border-slate-200">
                  <input v-model.trim="row.battery" class="input w-full" placeholder="电池度数" />
                </td>
                <td class="py-1 px-2 border border-slate-200">
                  <input v-model.number="row.qty" type="number" min="0" class="input w-full" placeholder="数量" />
                </td>
                <td class="py-1 px-2 border border-slate-200 text-center">
                  <button class="btn-ghost btn-sm" @click="form.trailerRequirements.splice(i, 1)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="md:col-span-2">
          <label class="label">项目描述<span class="text-slate-400 font-normal">（选填）</span></label>
          <textarea v-model="form.description" rows="3" class="input" />
        </div>
        <!-- 项目进展：新建时直接填写（必填，成为第一条进展记录）；编辑时只读，通过「新增进展」追加 -->
        <div v-if="!form.id" class="md:col-span-2">
          <label class="label">项目进展<span class="req">*</span><span class="text-slate-400 font-normal">（将作为第一条进展记录）</span></label>
          <textarea v-model="form.progress" rows="2" class="input" placeholder="当前项目进展说明" />
        </div>
        <div v-else class="md:col-span-2">
          <label class="label">进展记录<span class="text-slate-400 font-normal">（不可直接修改，点击「新增进展」追加本次内容）</span></label>
          <div class="flex items-center gap-2 mb-2">
            <input
              v-model.trim="progressInput"
              class="input"
              placeholder="填写本次进展内容"
              @keyup.enter="addProgress"
            />
            <button class="btn-ghost whitespace-nowrap shrink-0" :disabled="progressBusy" @click="addProgress">
              {{ progressBusy ? '保存中…' : '+ 新增进展' }}
            </button>
          </div>
          <!-- 时间轴（倒序，默认最近 5 条，下拉加载更早） -->
          <div v-if="progressItems.length" class="max-h-52 overflow-y-auto border border-slate-200 rounded-lg px-3.5 py-2.5">
            <div v-for="(p, i) in progressItems" :key="p.id" class="flex gap-2.5">
              <div class="flex flex-col items-center shrink-0">
                <span class="w-2 h-2 rounded-full bg-brand-500 mt-1.5" />
                <span v-if="i < progressItems.length - 1" class="w-px flex-1 bg-slate-200 min-h-[28px]" />
              </div>
              <div class="pb-3 min-w-0">
                <div class="text-sm text-slate-700 whitespace-pre-wrap break-words">{{ p.content }}</div>
                <div class="text-xs text-slate-400 mt-0.5">{{ p.createdByName || '—' }} · {{ fmtTime(p.createdAt) }}</div>
              </div>
            </div>
            <button
              v-if="progressItems.length < progressTotal"
              class="btn-ghost btn-sm w-full mt-1"
              :disabled="progressLoading"
              @click="loadMoreProgress"
            >
              {{ progressLoading ? '加载中…' : `加载更早记录（剩余 ${progressTotal - progressItems.length} 条）` }}
            </button>
          </div>
          <p v-else class="text-xs text-slate-400">暂无进展记录</p>
        </div>
      </div>
      <p class="mt-3 text-[11px] text-slate-400">创建人、创建时间、更新时间由系统自动记录，无需填写。</p>
      <p v-if="formError" class="mt-2 text-sm text-bad-600">{{ formError }}</p>
      <template #footer>
        <button class="btn-ghost" @click="formOpen = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
      </template>
    </ModalDialog>

    <!-- 项目详情（只读 · 展示编辑内所有信息 + 进展记录时间轴 + 可新增进展） -->
    <ModalDialog :open="detailOpen" title="项目详情" width="lg" @close="detailOpen = false">
      <div v-if="detailProject" class="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3">
        <div class="md:col-span-2">
          <label class="label">项目名称</label>
          <p class="text-sm text-slate-800 font-semibold">{{ detailProject.name }}</p>
        </div>
        <div>
          <label class="label">项目阶段</label>
          <p class="text-sm text-slate-700">{{ detailProject.stage }}% {{ detailProject.stageLabel }}</p>
        </div>
        <div>
          <label class="label">责任人</label>
          <p class="text-sm text-slate-700">{{ detailProject.owner }}</p>
        </div>
        <div>
          <label class="label">所属部门</label>
          <p class="text-sm text-slate-700">{{ detailProject.ownerDeptName || '—' }}</p>
        </div>
        <div>
          <label class="label">车头数量 / 挂车数量</label>
          <p class="text-sm text-slate-700">{{ detailProject.tractorDemand }} 辆 / {{ detailProject.trailerDemand }} 辆</p>
        </div>
        <div class="md:col-span-2">
          <label class="label">车头需求明细</label>
          <div v-if="detailProject.tractorRequirements.length" class="space-y-1.5">
            <div
              v-for="r in detailProject.tractorRequirements"
              :key="r.id"
              class="flex items-center gap-2 text-sm text-slate-700"
            >
              <span class="chip bg-brand-50 text-brand-700 border border-brand-100">{{ r.model || '未填型号' }}</span>
              <span class="text-slate-400">电池 {{ r.battery || '—' }}</span>
              <span class="font-semibold">{{ r.qty }} 辆</span>
            </div>
          </div>
          <p v-else class="text-xs text-slate-400">暂无车头需求明细</p>
        </div>
        <div class="md:col-span-2">
          <label class="label">挂车需求明细</label>
          <div v-if="detailProject.trailerRequirements.length" class="space-y-1.5">
            <div
              v-for="r in detailProject.trailerRequirements"
              :key="r.id"
              class="flex items-center gap-2 text-sm text-slate-700"
            >
              <span class="chip bg-brand-50 text-brand-700 border border-brand-100">{{ r.model || '未填型号' }}</span>
              <span class="text-slate-400">电池 {{ r.battery || '—' }}</span>
              <span class="font-semibold">{{ r.qty }} 辆</span>
            </div>
          </div>
          <p v-else class="text-xs text-slate-400">暂无挂车需求明细</p>
        </div>
        <div class="md:col-span-2">
          <label class="label">项目描述</label>
          <p class="text-sm text-slate-700 whitespace-pre-wrap">{{ detailProject.description || '—' }}</p>
        </div>
        <div class="md:col-span-2">
          <label class="label">
            项目进展（最近 {{ PROGRESS_PAGE_SIZE }} 条，倒序）
            <span v-if="auth.hasPerm('market.edit')" class="text-slate-400 font-normal">· 可在此追加本次进展</span>
          </label>
          <div v-if="auth.hasPerm('market.edit')" class="flex items-center gap-2 mb-2">
            <input
              v-model.trim="progressInput"
              class="input"
              placeholder="填写本次进展内容"
              @keyup.enter="addProgress"
            />
            <button class="btn-ghost whitespace-nowrap shrink-0" :disabled="progressBusy" @click="addProgress">
              {{ progressBusy ? '保存中…' : '+ 新增进展' }}
            </button>
          </div>
          <div v-if="progressItems.length" class="max-h-56 overflow-y-auto border border-slate-200 rounded-lg px-3.5 py-2.5">
            <div v-for="(p, i) in progressItems" :key="p.id" class="flex gap-2.5">
              <div class="flex flex-col items-center shrink-0">
                <span class="w-2 h-2 rounded-full bg-brand-500 mt-1.5" />
                <span v-if="i < progressItems.length - 1" class="w-px flex-1 bg-slate-200 min-h-[28px]" />
              </div>
              <div class="pb-3 min-w-0">
                <div class="text-sm text-slate-700 whitespace-pre-wrap break-words">{{ p.content }}</div>
                <div class="text-xs text-slate-400 mt-0.5">{{ p.createdByName || '—' }} · {{ fmtTime(p.createdAt) }}</div>
              </div>
            </div>
            <button
              v-if="progressItems.length < progressTotal"
              class="btn-ghost btn-sm w-full mt-1"
              :disabled="progressLoading"
              @click="loadMoreProgress"
            >
              {{ progressLoading ? '加载中…' : `加载更早记录（剩余 ${progressTotal - progressItems.length} 条）` }}
            </button>
          </div>
          <p v-else class="text-xs text-slate-400">暂无进展记录</p>
        </div>
        <div>
          <label class="label">创建人</label>
          <p class="text-sm text-slate-700">{{ detailProject.createdByName || '—' }}</p>
        </div>
        <div>
          <label class="label">创建 / 更新时间</label>
          <p class="text-sm text-slate-700">{{ fmtTime(detailProject.createdAt) }} / {{ fmtTime(detailProject.updatedAt) }}</p>
        </div>
      </div>
      <template #footer>
        <button class="btn-primary" @click="detailOpen = false">关闭</button>
      </template>
    </ModalDialog>

    <!-- 删除确认 -->
    <ModalDialog :open="!!deleteTarget" title="确认删除项目" width="sm" @close="deleteTarget = null">
      <p class="text-sm text-slate-600">
        将删除项目「{{ deleteTarget?.name }}」（{{ deleteTarget?.id }}）。该操作不可撤销，驾驶舱漏斗会同步减少。
      </p>
      <template #footer>
        <button class="btn-ghost" @click="deleteTarget = null">取消</button>
        <button class="btn-danger" @click="doDelete">确认删除</button>
      </template>
    </ModalDialog>

    <!-- 批量导入（含下载模板 + 上传 + 结果） -->
    <ModalDialog :open="importOpen" title="批量导入" width="lg" @close="importOpen = false">
      <div class="space-y-4">
        <p class="text-sm text-slate-500">
          先下载标准模板填写，再上传。模板仅含项目信息（项目名称 / 进展 / 描述 / 阶段 / 责任人 / 所属部门），
          <b>车头需求、挂车需求不在导入范围内</b>，导入后请在系统「编辑项目」中补充车辆型号、电池度数与数量。
        </p>
        <div class="flex flex-wrap items-center gap-3">
          <button class="btn-ghost" @click="download(marketApi.templateUrl(), '市场项目导入标准模板.xlsx')">下载模板</button>
          <label v-if="auth.hasPerm('market.import')" class="btn-primary cursor-pointer">
            选择文件导入
            <input type="file" accept=".xlsx" class="hidden" @change="onImport" />
          </label>
        </div>
        <div v-if="importResult">
          <p class="text-sm" :class="importResult.imported ? 'text-good-700' : 'text-bad-700'">
            {{ importResult.imported ? `成功导入 ${importResult.imported} 行。` : '存在错误行，本次未写入任何数据。' }}
          </p>
          <div v-if="importResult.errors.length" class="mt-3 max-h-72 overflow-y-auto border border-slate-200 rounded-lg">
            <table class="w-full">
              <thead class="sticky top-0">
                <tr>
                  <th class="th w-20">行号</th>
                  <th class="th w-40">字段</th>
                  <th class="th">错误说明</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(e, i) in importResult.errors" :key="i" class="border-b border-slate-100 bg-bad-50/40">
                  <td class="td">{{ e.row }}</td>
                  <td class="td text-bad-700 font-semibold">{{ e.field }}</td>
                  <td class="td whitespace-normal">{{ e.msg }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <template #footer>
        <button class="btn-primary" @click="importOpen = false">关闭</button>
      </template>
    </ModalDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { dictApi, downloadFile, marketApi, metaApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { MARKET_STAGE_LABELS } from '@/types'
import type {
  ImportResult,
  MarketOwner,
  MarketProjectItem,
  MarketStage,
  ProjectProgressItem,
  ProjectRequirementItem,
} from '@/types'

const auth = useAuthStore()
const app = useAppStore()
const router = useRouter()
const download = downloadFile

async function onExportMarket() {
  try {
    await marketApi.exportCreate()
    app.toast('已生成导出记录，请前往「下载中心」下载')
    router.push('/downloads')
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

/** 行高：绑定账号偏好（default/high/ultra），切换后写入后端、下次登录仍生效 */
const rowHeightSel = ref<'default' | 'high' | 'ultra'>((auth.rowHeight as 'default' | 'high' | 'ultra') || 'default')
const rowHeightClass = computed(() => `rh-${rowHeightSel.value}`)
function onRowHeightChange() {
  auth.updatePreferences({ rowHeight: rowHeightSel.value }).catch(() => {})
}

const STAGES: MarketStage[] = [10, 25, 50, 75, 90, 100]

/** 系统默认市场部 ID · 与后端 DEFAULT_MARKET_DEPT_ID 对应（用于责任人范围提示文案） */
const MARKET_DEPT_ID = 'D01'

/** 阶段徽章配色：由浅入深，与驾驶舱漏斗色阶一致 */
const STAGE_CHIP: Record<number, string> = {
  10: 'bg-slate-100 text-slate-600 border-slate-200',
  25: 'bg-brand-50 text-brand-700 border-brand-100',
  50: 'bg-brand-50 text-brand-700 border-brand-100',
  75: 'bg-brand-100 text-brand-700 border-brand-200',
  90: 'bg-brand-100 text-brand-800 border-brand-200',
  100: 'bg-good-50 text-good-700 border-good-100',
}

const projects = ref<MarketProjectItem[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const stageFilter = ref<number | ''>('')
/** 责任人候选：仅市场部及其下属部门内的启用账号 */
const marketOwners = ref<MarketOwner[]>([])
/** 数据字典：车辆型号 / 挂车型号下拉项 */
const vehicleModels = ref<string[]>([])
const trailerModels = ref<string[]>([])

const PAGE_SIZE = 50
const page = ref(1)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function sumOf(field: 'tractorDemand' | 'trailerDemand') {
  return projects.value.reduce((acc, p) => acc + (p[field] || 0), 0)
}

/** ISO 时间 → 本地可读格式（与任务管理同一套） */
function fmtTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

const formOpen = ref(false)
const saving = ref(false)
const formError = ref('')
const form = reactive({
  id: '',
  name: '',
  description: '',
  progress: '',
  stage: 10 as MarketStage,
  owner: '',
  ownerDeptId: '',
  ownerDeptName: '',
  tractorRequirements: [] as ProjectRequirementItem[],
  trailerRequirements: [] as ProjectRequirementItem[],
})
const deleteTarget = ref<MarketProjectItem | null>(null)

/* ---------------- 进展记录（时间轴）· 编辑/详情共用 ---------------- */

/** 每页条数：默认展示最近 5 条，下拉加载更早记录 */
const PROGRESS_PAGE_SIZE = 5
/** 进展记录展示对象：编辑弹窗与详情弹窗共用同一份（同一时间只开一个） */
const detailOpen = ref(false)
const detailProject = ref<MarketProjectItem | null>(null)
/** 当前正在操作进展记录的项目 ID（编辑或详情），addProgress 统一使用 */
const progressOwnerId = ref('')
const progressItems = ref<ProjectProgressItem[]>([])
const progressTotal = ref(0)
const progressPage = ref(1)
const progressLoading = ref(false)
const progressInput = ref('')
const progressBusy = ref(false)

function resetProgress() {
  progressItems.value = []
  progressTotal.value = 0
  progressPage.value = 1
  progressInput.value = ''
}

/** 拉取进展记录（倒序分页）；append=true 时追加（下拉加载更早记录） */
async function fetchProgress(projectId: string, p: number, append = false) {
  progressLoading.value = true
  try {
    const res = await marketApi.progressList(projectId, { page: p, size: PROGRESS_PAGE_SIZE })
    progressItems.value = append ? [...progressItems.value, ...res.items] : res.items
    progressTotal.value = res.total
    progressPage.value = p
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    progressLoading.value = false
  }
}

function loadMoreProgress() {
  if (progressOwnerId.value) fetchProgress(progressOwnerId.value, progressPage.value + 1, true)
}

/** 追加一条进展记录：置顶插入 + 同步列表里的最新进展快照 */
async function addProgress() {
  const content = progressInput.value.trim()
  if (!content) {
    app.toast('请填写本次进展内容', 'error')
    return
  }
  if (!progressOwnerId.value) return
  progressBusy.value = true
  try {
    const created = await marketApi.progressAdd(progressOwnerId.value, content)
    progressItems.value = [created, ...progressItems.value]
    progressTotal.value += 1
    progressInput.value = ''
    // 列表「项目进展」列同步更新为最新一条
    const t = projects.value.find((x) => x.id === progressOwnerId.value)
    if (t) t.latestProgress = created.content
    app.toast('已添加进展')
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    progressBusy.value = false
  }
}

/** 详情（只读）：展示编辑内所有信息 + 进展记录时间轴 */
function openDetail(p: MarketProjectItem) {
  detailProject.value = p
  detailOpen.value = true
  progressOwnerId.value = p.id
  resetProgress()
  fetchProgress(p.id, 1)
}

const importOpen = ref(false)
const importResult = ref<ImportResult | null>(null)

async function load() {
  loading.value = true
  try {
    const res = await marketApi.list({
      keyword: keyword.value,
      stage: stageFilter.value,
      page: page.value,
      size: PAGE_SIZE,
    })
    projects.value = res.items
    total.value = res.total
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  load()
}

function goPage(n: number) {
  const next = Math.min(Math.max(1, n), pageCount.value)
  if (next === page.value) return
  page.value = next
  load()
}

function openForm(p?: MarketProjectItem) {
  formError.value = ''
  if (p) {
    const owner = marketOwners.value.find((o) => o.name === p.owner)
    Object.assign(form, {
      id: p.id,
      name: p.name,
      description: p.description,
      progress: '',
      stage: p.stage,
      owner: p.owner,
      ownerDeptId: p.ownerDeptId ?? owner?.deptId ?? '',
      ownerDeptName: p.ownerDeptName || owner?.deptName || '',
      tractorRequirements: (p.tractorRequirements || []).map((r) => ({ ...r })),
      trailerRequirements: (p.trailerRequirements || []).map((r) => ({ ...r })),
    })
    // 编辑模式加载进展记录（新建无需）；progressOwnerId 供 addProgress 使用
    progressOwnerId.value = p.id
    resetProgress()
    fetchProgress(p.id, 1)
  } else {
    const first = marketOwners.value[0]
    Object.assign(form, {
      id: '',
      name: '',
      description: '',
      progress: '',
      stage: 10,
      owner: first?.name ?? auth.user?.name ?? '',
      ownerDeptId: first?.deptId ?? MARKET_DEPT_ID,
      ownerDeptName: first?.deptName ?? '',
      tractorRequirements: [],
      trailerRequirements: [],
    })
    progressOwnerId.value = ''
    resetProgress()
  }
  formOpen.value = true
}

/** 选择责任人后，自动带出其直接所属部门（二级/三级部门均可） */
function onOwnerChange() {
  const o = marketOwners.value.find((x) => x.name === form.owner)
  form.ownerDeptId = o?.deptId ?? ''
  form.ownerDeptName = o?.deptName ?? ''
}

async function save() {
  formError.value = ''
  if (!form.name) return (formError.value = '项目名称不能为空')
  if (!form.owner) return (formError.value = '请选择责任人')
  if (!form.ownerDeptId) return (formError.value = '请选择市场部及下属部门的责任人')
  // 需求明细：每条数量不可为负
  for (const r of [...form.tractorRequirements, ...form.trailerRequirements]) {
    if (!(r.qty >= 0)) return (formError.value = '需求数量不能为负')
  }
  // 进展必填（新建时填写，成为第一条进展记录；编辑不可直接改进展，只能「新增进展」）
  if (!form.id && !form.progress.trim()) return (formError.value = '项目进展不能为空')

  saving.value = true
  // 请求体使用后端约定的 snake_case 字段；车头/挂车需求以明细子列表提交，汇总由后端计算
  const payload: Record<string, unknown> = {
    name: form.name,
    description: form.description,
    stage: form.stage,
    owner: form.owner,
    owner_dept_id: form.ownerDeptId,
    tractorRequirements: form.tractorRequirements.map((r) => ({ model: r.model, battery: r.battery, qty: Number(r.qty) || 0 })),
    trailerRequirements: form.trailerRequirements.map((r) => ({ model: r.model, battery: r.battery, qty: Number(r.qty) || 0 })),
  }
  if (!form.id) payload.progress = form.progress // 仅创建携带项目进展；编辑不可直接改进展
  try {
    if (form.id) await marketApi.update(form.id, payload)
    else await marketApi.create(payload)
    app.toast('保存成功')
    formOpen.value = false
    await load()
  } catch (e) {
    formError.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    await marketApi.remove(deleteTarget.value.id)
    app.toast('已删除')
    deleteTarget.value = null
    await load()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

async function onImport(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    importResult.value = await marketApi.importFile(file)
    importOpen.value = true
    if (importResult.value.imported) {
      app.toast(`成功导入 ${importResult.value.imported} 行`)
      await load()
    }
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    input.value = ''
  }
}

/** 加载数据字典下拉项（车辆型号 / 挂车型号） */
async function loadDictModels() {
  try {
    const [veh, tra] = await Promise.all([dictApi.list('vehicle_model'), dictApi.list('trailer_model')])
    vehicleModels.value = (veh[0]?.items || []).map((i) => i.value)
    trailerModels.value = (tra[0]?.items || []).map((i) => i.value)
  } catch {
    /* 字典未配置时下拉为空，仍可手动录入 */
  }
}

onMounted(async () => {
  try {
    marketOwners.value = await metaApi.marketOwners()
  } catch {
    /* 忽略字典加载失败 */
  }
  await loadDictModels()
  await load()
})
</script>
