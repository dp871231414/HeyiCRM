<template>
  <div class="space-y-4">
    <!-- 工具条 -->
    <div class="card p-3.5 flex flex-wrap items-center gap-2.5">
      <input v-model.trim="keyword" class="input !w-56" placeholder="搜索任务ID / 名称 / 责任人" @keyup.enter="applyFilters" />
      <select v-model="deptFilter" class="input !w-44" @change="applyFilters">
        <option value="">全部责任部门</option>
        <option v-for="o in orgs" :key="o.id" :value="o.id">{{ '　'.repeat(o.depth) }}{{ o.name }}</option>
      </select>
      <select v-model="statusFilter" class="input !w-36" @change="applyFilters">
        <option value="">全部状态</option>
        <option value="done">已完成</option>
        <option value="normal">正常</option>
        <option value="due_soon">临期</option>
        <option value="overdue">逾期</option>
        <option value="risk">异常</option>
      </select>
      <button class="btn-ghost" @click="applyFilters">查询</button>

      <div class="ml-auto flex items-center gap-2">
        <div class="flex items-center rounded-xl border border-slate-200/80 p-0.5 bg-slate-100/70">
          <button
            class="px-2.5 py-1 rounded-lg text-xs font-semibold transition-all duration-200"
            :class="!groupByDept ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
            @click="switchView(false)"
          >
            列表
          </button>
          <button
            class="px-2.5 py-1 rounded-lg text-xs font-semibold transition-all duration-200"
            :class="groupByDept ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
            @click="switchView(true)"
          >
            分组视图
          </button>
        </div>
        <!-- 行高设置：按账号记忆，下次登录仍生效；选择后所有行高一次性调整 -->
        <div class="flex items-center gap-1.5 ml-2">
          <span class="text-xs text-slate-400">行高</span>
          <select v-model="rowHeightSel" class="input !w-32" @change="onRowHeightChange">
            <option value="default">默认</option>
            <option value="high">高（2X）</option>
            <option value="ultra">超高（3X）</option>
          </select>
        </div>
        <button class="btn-ghost" @click="download(taskApi.exportUrl(), '重点任务清单.xlsx')">导出</button>
        <button v-if="auth.hasPerm('task.import')" class="btn-ghost" @click="importOpen = true">批量导入</button>
        <button v-if="auth.hasPerm('task.edit')" class="btn-primary" @click="openForm()">新建任务</button>
      </div>
    </div>

    <!-- 汇总 -->
    <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500 px-1">
      <span>共 <b class="text-slate-800">{{ total }}</b> 项任务</span>
      <span>已完成 <b class="text-good-600">{{ countBy('done') }}</b></span>
      <span>临期 <b class="text-warn-600">{{ countBy('due_soon') }}</b></span>
      <span>逾期 <b class="text-bad-600">{{ countBy('overdue') }}</b></span>
      <span>异常 <b class="text-bad-600">{{ countBy('risk') }}</b></span>
    </div>
    <p v-if="groupByDept && total > tasks.length" class="px-1 text-xs text-warn-600">
      分组视图最多加载 {{ GROUP_FETCH_SIZE }} 条，当前共 {{ total }} 条；请用上方条件缩小范围后再查看。
    </p>

    <!-- 表格 -->
    <div class="card overflow-hidden">
      <div v-if="loading" class="p-10 text-center text-slate-400 text-sm">加载中…</div>
      <div v-else-if="!tasks.length" class="p-10 text-center text-slate-400 text-sm">暂无任务</div>
      <div v-else class="overflow-x-auto">
        <table :class="rowHeightClass" class="table-freeze table-fixed w-[2219px]">
          <thead>
            <tr class="border-b border-slate-200">
              <th class="th col-id w-[96px]">任务ID</th>
              <th class="th col-maintask w-[213px]">主任务</th>
              <th class="th col-name w-[213px]">任务名称</th>
              <th class="th w-[307px]">进展描述</th>
              <th class="th w-[100px]">责任人</th>
              <th class="th w-[120px]">责任部门</th>
              <th class="th w-[100px]">创建人</th>
              <th class="th w-[100px] text-right">目标</th>
              <th class="th w-[110px] text-right">已完成</th>
              <th class="th w-[130px]">完成进度</th>
              <th class="th w-[110px]">状态</th>
              <th class="th w-[180px]">计划起止</th>
              <th class="th w-[140px]">创建时间</th>
              <th class="th w-[140px]">更新时间</th>
              <th class="th col-ops w-[160px] text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in rows" :key="row.key">
              <!-- 分组小标题（按部门分组视图） -->
              <tr v-if="row.kind === 'group'" class="bg-slate-100">
                <td :colspan="COL_COUNT" class="td font-bold text-slate-700">
                  <span class="group-title">
                    {{ row.deptName }}
                    <span class="ml-1.5 text-[11px] font-normal text-slate-400">{{ row.count }} 项任务</span>
                  </span>
                </td>
              </tr>
              <!-- 该部门的分页器（仅当该组超过一页时出现） -->
              <tr v-else-if="row.kind === 'pager'" class="border-b border-slate-100 bg-white">
                <td :colspan="COL_COUNT" class="td !py-2">
                  <div class="group-title">
                    <PaginationBar
                      :page="row.page"
                      :page-count="row.pageCount"
                      :total="row.total"
                      @update:page="(n) => setGroupPage(row.deptId, n)"
                    />
                  </div>
                </td>
              </tr>
              <!-- 任务行 -->
              <tr v-else class="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td class="td col-id font-mono text-xs text-slate-500">{{ row.task.id }}</td>
                <td class="td col-maintask w-[213px]">
                  <div class="cell-c text-slate-500" :title="row.task.mainTaskName || '空'">{{ row.task.mainTaskName || '空' }}</div>
                </td>
                <td class="td col-name w-[213px]">
                  <div class="cell-c font-semibold text-slate-800" :title="row.task.parent">{{ row.task.parent }}</div>
                </td>
                <td class="td w-[307px]">
                  <div class="cell-c text-slate-600" :title="row.task.latestProgress || '—'">{{ row.task.latestProgress || '—' }}</div>
                </td>
                <td class="td">{{ row.task.owner }}</td>
                <td class="td">{{ row.task.deptName }}</td>
                <td class="td text-slate-500">{{ row.task.createdByName || '—' }}</td>
                <td class="td text-right font-mono">{{ fmt(row.task.target) }}<span class="text-[11px] text-slate-400 ml-0.5">{{ row.task.unit }}</span></td>
                <td class="td text-right font-mono">{{ fmt(row.task.done) }}</td>
                <td class="td">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden min-w-[46px]">
                      <div class="h-full rounded-full" :class="progressBar(row.task)" :style="{ width: Math.min(100, row.task.progress) + '%' }" />
                    </div>
                    <span class="text-xs font-bold text-slate-600 w-9 text-right">{{ row.task.progress }}%</span>
                  </div>
                </td>
                <td class="td"><StatusBadge :status="row.task.statusLevel" :text="row.task.statusLabel" /></td>
                <td class="td text-xs text-slate-500">{{ row.task.startDate }} ~ {{ row.task.endDate }}</td>
                <td class="td text-xs text-slate-500">{{ fmtTime(row.task.createdAt) }}</td>
                <td class="td text-xs text-slate-500">{{ fmtTime(row.task.updatedAt) }}</td>
                <td class="td col-ops text-right whitespace-nowrap">
                  <button v-if="auth.hasPerm('task.detail')" class="btn-ghost btn-sm" @click="openDetail(row.task)">详情</button>
                  <button v-if="auth.hasPerm('task.edit')" class="btn-ghost btn-sm ml-1.5" @click="openForm(row.task)">编辑</button>
                  <button
                    v-if="auth.hasPerm('task.delete')"
                    class="btn-danger btn-sm ml-1.5"
                    @click="confirmDelete(row.task)"
                  >
                    删除
                  </button>
                  <span v-if="!auth.hasAnyPerm(['task.detail', 'task.edit', 'task.delete'])" class="text-xs text-slate-300">—</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      <!-- 平铺视图分页器：始终显示（只有一页时按钮为禁用态），便于随时看到页数与总数 -->
      <div
        v-if="!groupByDept"
        class="flex items-center justify-between border-t border-slate-100 px-3.5 py-2.5"
      >
        <span class="text-xs text-slate-400">每页最多 {{ PAGE_SIZE }} 条</span>
        <PaginationBar :page="page" :page-count="pageCount" :total="total" @update:page="goPage" />
      </div>
    </div>

    <!-- 新建 / 编辑 -->
    <ModalDialog :open="formOpen" :title="form.id ? '编辑任务' : '新建任务'" width="lg" @close="formOpen = false">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="md:col-span-2">
          <label class="label">任务名称<span class="req">*</span></label>
          <input v-model.trim="form.parent" class="input" placeholder="如：完成全年营收目标 10.2 亿" />
        </div>
        <div>
          <label class="label">主任务<span class="req">*</span><span class="text-slate-400 font-normal">（不选默认「空」，展示「名称 责任人」）</span></label>
          <div v-if="addingMainTask" class="flex items-center gap-2">
            <input
              v-model.trim="newMainTaskName"
              class="input"
              placeholder="输入新主任务名称"
              @keyup.enter="confirmAddMainTask"
            />
            <button class="btn-ghost" :disabled="addingMainTaskBusy" @click="confirmAddMainTask">
              {{ addingMainTaskBusy ? '创建中…' : '确定' }}
            </button>
            <button class="btn-ghost" @click="addingMainTask = false">取消</button>
          </div>
          <div v-else class="flex items-center gap-2">
            <div class="relative flex-1 min-w-0">
              <button
                type="button"
                class="input flex items-center justify-between w-full text-left"
                @click="mtDropdownOpen = !mtDropdownOpen"
              >
                <span class="truncate">{{ selectedMainTaskLabel || '请选择主任务' }}</span>
                <span class="text-slate-400 ml-2">▾</span>
              </button>
              <!-- 点击空白处关闭下拉 -->
              <div v-if="mtDropdownOpen" class="fixed inset-0 z-10" @click="mtDropdownOpen = false" />
              <div
                v-if="mtDropdownOpen"
                class="absolute z-20 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-lg max-h-64 overflow-auto"
              >
                <button
                  v-for="m in mainTasks"
                  :key="m.id"
                  type="button"
                  class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-slate-50"
                  :class="form.mainTaskId === m.id ? 'bg-brand-50' : ''"
                  @click="selectMainTask(m.id)"
                >
                  <span class="flex-1 min-w-0 truncate">
                    <template v-if="renamingId === m.id">
                      <input
                        v-model.trim="renameValue"
                        class="input !py-0.5 !px-1.5 text-xs w-full"
                        :disabled="renamingBusy"
                        @click.stop
                        @keyup.enter="confirmRename(m)"
                        @keyup.esc="cancelRename"
                      />
                    </template>
                    <template v-else>
                      <span>{{ m.name }}{{ m.isSystem ? '（默认）' : '' }}</span>
                      <!-- 展示主任务责任人（回填自首个关联任务）；创建人仅存数据表不在此体现 -->
                      <span v-if="m.ownerName" class="text-slate-400 text-xs"> {{ m.ownerName }}</span>
                    </template>
                  </span>
                  <span v-if="renamingId === m.id" class="flex items-center gap-1 shrink-0" @click.stop>
                    <button type="button" class="text-good-600 text-xs" :disabled="renamingBusy" @click="confirmRename(m)">保存</button>
                    <button type="button" class="text-slate-400 text-xs" :disabled="renamingBusy" @click="cancelRename">取消</button>
                  </span>
                  <button
                    v-else-if="auth.hasPerm('task.edit') && !m.isSystem"
                    type="button"
                    class="text-slate-400 hover:text-brand-600 shrink-0"
                    title="修改主任务名称"
                    @click.stop="startRename(m)"
                  >
                    ✎
                  </button>
                </button>
              </div>
            </div>
            <!-- 新增主任务：常显在下拉选择框右侧 -->
            <button v-if="auth.hasPerm('task.edit')" class="btn-ghost whitespace-nowrap shrink-0" @click="addingMainTask = true">
              + 新增
            </button>
          </div>
        </div>
        <div>
          <label class="label">责任人<span class="req">*</span></label>
          <select v-model="form.owner" class="input">
            <option v-for="o in owners" :key="o.id" :value="o.name">{{ o.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">责任部门<span class="req">*</span></label>
          <select v-model="form.deptId" class="input">
            <option v-for="o in orgs" :key="o.id" :value="o.id">{{ '　'.repeat(o.depth) }}{{ o.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">是否异常</label>
          <select v-model="form.abnormal" class="input">
            <option :value="false">否</option>
            <option :value="true">是</option>
          </select>
        </div>
        <div>
          <label class="label">目标（数字，非量化任务填 1）<span class="req">*</span></label>
          <input v-model.number="form.target" type="number" class="input" placeholder="如：46000" />
        </div>
        <div>
          <label class="label">已完成（非量化任务未完成 0 / 完成 1）</label>
          <input v-model.number="form.done" type="number" class="input" placeholder="如：31800" />
        </div>
        <div>
          <label class="label">数量单位</label>
          <input v-model.trim="form.unit" class="input" placeholder="万元 / 辆 / 项 / %" />
        </div>
        <div>
          <label class="label">完成进度（系统计算）</label>
          <input class="input" :value="previewProgress + '%'" disabled />
        </div>
        <div>
          <label class="label">计划开始日期<span class="req">*</span></label>
          <input v-model="form.startDate" type="date" class="input" />
        </div>
        <div>
          <label class="label">计划结束日期<span class="req">*</span></label>
          <input v-model="form.endDate" type="date" class="input" />
        </div>
        <div class="md:col-span-2">
          <label class="label">任务描述<span class="req">*</span></label>
          <textarea v-model="form.description" rows="2" class="input" placeholder="任务的背景、交付要求与关键说明" />
        </div>
        <!-- 进展描述：新建时直接填写（必填，成为第一条进展记录）；编辑时只读，通过「新增进展」追加 -->
        <div v-if="!form.id" class="md:col-span-2">
          <label class="label">进展描述<span class="req">*</span><span class="text-slate-400 font-normal">（将作为第一条进展记录）</span></label>
          <textarea v-model="form.note" rows="2" class="input" placeholder="当前进展说明" />
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
      <p v-if="formError" class="mt-3 text-sm text-bad-600">{{ formError }}</p>
      <template #footer>
        <button class="btn-ghost" @click="formOpen = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
      </template>
    </ModalDialog>

    <!-- 任务详情（只读 · 展示编辑内所有信息 + 进展记录时间轴） -->
    <ModalDialog :open="detailOpen" title="任务详情" width="lg" @close="detailOpen = false">
      <div v-if="detailTask" class="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3">
        <div class="md:col-span-2">
          <label class="label">任务名称</label>
          <p class="text-sm text-slate-800 font-semibold">{{ detailTask.parent }}</p>
        </div>
        <div>
          <label class="label">主任务</label>
          <p class="text-sm text-slate-700">{{ detailTask.mainTaskName || '空' }}</p>
        </div>
        <div>
          <label class="label">责任人</label>
          <p class="text-sm text-slate-700">{{ detailTask.owner }}</p>
        </div>
        <div>
          <label class="label">责任部门</label>
          <p class="text-sm text-slate-700">{{ detailTask.deptName }}</p>
        </div>
        <div>
          <label class="label">是否异常</label>
          <p class="text-sm text-slate-700">{{ detailTask.abnormal ? '是' : '否' }}</p>
        </div>
        <div>
          <label class="label">目标</label>
          <p class="text-sm text-slate-700">{{ fmt(detailTask.target) }} {{ detailTask.unit }}</p>
        </div>
        <div>
          <label class="label">已完成</label>
          <p class="text-sm text-slate-700">{{ fmt(detailTask.done) }} {{ detailTask.unit }}</p>
        </div>
        <div>
          <label class="label">完成进度</label>
          <p class="text-sm text-slate-700">{{ detailTask.progress }}%</p>
        </div>
        <div>
          <label class="label">状态</label>
          <p class="text-sm"><StatusBadge :status="detailTask.statusLevel" :text="detailTask.statusLabel" /></p>
        </div>
        <div class="md:col-span-2">
          <label class="label">计划起止</label>
          <p class="text-sm text-slate-700">{{ detailTask.startDate }} ~ {{ detailTask.endDate }}</p>
        </div>
        <div class="md:col-span-2">
          <label class="label">任务描述</label>
          <p class="text-sm text-slate-700 whitespace-pre-wrap">{{ detailTask.description || '—' }}</p>
        </div>
        <div class="md:col-span-2">
          <label class="label">进展记录（最近 {{ PROGRESS_PAGE_SIZE }} 条，倒序）</label>
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
          <p class="text-sm text-slate-700">{{ detailTask.createdByName || '—' }}</p>
        </div>
        <div>
          <label class="label">创建 / 更新时间</label>
          <p class="text-sm text-slate-700">{{ fmtTime(detailTask.createdAt) }} / {{ fmtTime(detailTask.updatedAt) }}</p>
        </div>
      </div>
      <template #footer>
        <button class="btn-primary" @click="detailOpen = false">关闭</button>
      </template>
    </ModalDialog>

    <!-- 删除确认 -->
    <ModalDialog :open="!!deleteTarget" title="确认删除任务" width="sm" @close="deleteTarget = null">
      <p class="text-sm text-slate-600">
        将删除任务「{{ deleteTarget?.parent }}」（{{ deleteTarget?.id }}）。该操作不可撤销。
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
          先下载标准模板填写，再上传。模板中「任务分类」列会对应到主任务（主任务不存在时自动新建）。
        </p>
        <div class="flex flex-wrap items-center gap-3">
          <button class="btn-ghost" @click="download(taskApi.templateUrl(), '重点任务导入标准模板.xlsx')">下载模板</button>
          <label v-if="auth.hasPerm('task.import')" class="btn-primary cursor-pointer">
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

import { downloadFile, mainTaskApi, metaApi, taskApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { ImportResult, MainTask, TaskItem, TaskProgressItem } from '@/types'
import { fmt } from '@/utils/format'

/** 系统默认主任务 ID（与后端 MT_NONE 约定一致）：任务未选主任务时默认关联它 */
const MT_NONE_ID = 'MT_NONE'

const auth = useAuthStore()
const app = useAppStore()

/** 行高：绑定账号偏好（default/high/ultra），切换后写入后端、下次登录仍生效 */
const rowHeightSel = ref<'default' | 'high' | 'ultra'>((auth.rowHeight as 'default' | 'high' | 'ultra') || 'default')
const rowHeightClass = computed(() => `rh-${rowHeightSel.value}`)
function onRowHeightChange() {
  // 乐观更新已在 v-model 生效；后台失败不影响界面，仅下次同步
  auth.updatePreferences({ rowHeight: rowHeightSel.value }).catch(() => {})
}

const tasks = ref<TaskItem[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const deptFilter = ref('')
const statusFilter = ref('')
const orgs = ref<{ id: string; name: string; depth: number }[]>([])
const owners = ref<{ id: string; name: string }[]>([])
/** 主任务（原任务分类）下拉选项 */
const mainTasks = ref<MainTask[]>([])
/** 新增主任务内联输入 */
const addingMainTask = ref(false)
const addingMainTaskBusy = ref(false)
const newMainTaskName = ref('')
/** 主任务自定义下拉：展开状态 + 内联改名 */
const mtDropdownOpen = ref(false)
const renamingId = ref('')
const renameValue = ref('')
const renamingBusy = ref(false)

/** 当前选中主任务的展示文案：名称 + 责任人（如「注册新公司 胡国海」），系统默认「空」标记。
 *  按需求展示主任务责任人（回填字段）；创建人仅存数据表，不在前端体现。 */
const selectedMainTaskLabel = computed(() => {
  const m = mainTasks.value.find((x) => x.id === form.mainTaskId)
  if (!m) return ''
  return `${m.name}${m.isSystem ? '（默认）' : ''}${m.ownerName ? ` ${m.ownerName}` : ''}`
})

function selectMainTask(id: string) {
  form.mainTaskId = id
  mtDropdownOpen.value = false
}

function startRename(m: MainTask) {
  renamingId.value = m.id
  renameValue.value = m.name
}
function cancelRename() {
  renamingId.value = ''
  renameValue.value = ''
}
async function confirmRename(m: MainTask) {
  const name = renameValue.value.trim()
  if (!name) {
    app.toast('主任务名称不能为空', 'error')
    return
  }
  renamingBusy.value = true
  try {
    const updated = await mainTaskApi.rename(m.id, name)
    const idx = mainTasks.value.findIndex((x) => x.id === m.id)
    if (idx >= 0) mainTasks.value[idx] = { ...mainTasks.value[idx], ...updated }
    cancelRename()
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    renamingBusy.value = false
  }
}

/** 视图模式：false=平铺列表，true=按部门分组（每组带小标题） */
const groupByDept = ref(false)

/** 平铺视图每页条数（后端分页） */
const PAGE_SIZE = 50
/** 分组视图下每个部门每页条数（各组独立分页） */
const GROUP_PAGE_SIZE = 20
/** 分组视图一次拉取的条数上限（需全量才能按部门分组） */
const GROUP_FETCH_SIZE = 2000

const page = ref(1)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
/** 分组视图下每个部门的当前页（key=部门 ID） */
const groupPages = reactive<Record<string, number>>({})

type TaskRow =
  | {
      kind: 'group'
      key: string
      deptId: string
      deptName: string
      count: number
      page: number
      pageCount: number
    }
  | { kind: 'task'; key: string; task: TaskItem }
  | { kind: 'pager'; key: string; deptId: string; page: number; pageCount: number; total: number }

/**
 * 表格渲染行。分组模式下在每个部门前插入一行小标题、末尾插入该组的分页器，
 * 与任务行共用同一张表 —— 既不必为分组复制一遍行模板，列宽也保持一致。
 */
const rows = computed<TaskRow[]>(() => {
  if (!groupByDept.value) return tasks.value.map((t) => ({ kind: 'task', key: t.id, task: t }))
  const buckets = new Map<string, TaskItem[]>()
  for (const t of tasks.value) {
    const k = t.deptId || '__none__'
    const list = buckets.get(k)
    if (list) list.push(t)
    else buckets.set(k, [t])
  }
  const out: TaskRow[] = []
  for (const [k, items] of buckets) {
    // 分组视图排序：部门内 → 主任务（按不可变 mainTaskId 归类，同一主任务跨人员排在一起，无主任务 MT_NONE 置后）
    //   → 创建时间倒序（同主任务内新任务在上）。
    // 关键点：主任务优先于人员 —— 同一主任务下的任务必须相邻（如 T20260016 与 T202601 同属
    // 「华东大区营收达成」，即使责任人不相同也要排在一起）；人员维度不再参与排序。
    const sorted = [...items].sort((a, b) => {
      const ae = a.mainTaskId === MT_NONE_ID ? 1 : 0
      const be = b.mainTaskId === MT_NONE_ID ? 1 : 0
      if (ae !== be) return ae - be
      if (a.mainTaskId !== b.mainTaskId) return (a.mainTaskId || '') < (b.mainTaskId || '') ? -1 : 1
      const at = new Date(a.createdAt).getTime() || 0
      const bt = new Date(b.createdAt).getTime() || 0
      return bt - at
    })
    const pc = Math.max(1, Math.ceil(sorted.length / GROUP_PAGE_SIZE))
    const cur = Math.min(Math.max(1, groupPages[k] ?? 1), pc)
    out.push({
      kind: 'group',
      key: `g:${k}`,
      deptId: k,
      deptName: sorted[0]?.deptName || '未指定部门',
      count: sorted.length,
      page: cur,
      pageCount: pc,
    })
    const start = (cur - 1) * GROUP_PAGE_SIZE
    for (const t of sorted.slice(start, start + GROUP_PAGE_SIZE)) {
      out.push({ kind: 'task', key: t.id, task: t })
    }
    // 每个部门都带分页器（只有一页时按钮为禁用态），页序与总数在分页器里体现
    out.push({ kind: 'pager', key: `p:${k}`, deptId: k, page: cur, pageCount: pc, total: sorted.length })
  }
  return out
})

/** 表格列数（分组标题行需整行跨列） */
const COL_COUNT = 15

/** ISO 时间 → 本地可读格式。后端返回带时区，须转本地时区展示 */
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
  parent: '',
  mainTaskId: '',
  description: '',
  abnormal: false,
  target: 1,
  done: 0,
  unit: '',
  note: '',
  startDate: new Date().toISOString().slice(0, 10),
  endDate: '',
  deptId: '',
  owner: '',
})

/** 系统默认主任务 ID（用于新建任务未选主任务时回填） */
function defaultMainTaskId(): string {
  return mainTasks.value.find((m) => m.isSystem)?.id ?? MT_NONE_ID
}

const deleteTarget = ref<TaskItem | null>(null)
const importOpen = ref(false)
const importResult = ref<ImportResult | null>(null)

const previewProgress = computed(() =>
  form.target > 0 ? Math.round((form.done / form.target) * 100) : 0,
)

/* ---------------- 进展记录（时间轴）· 编辑/详情共用 ---------------- */

/** 每页条数：默认展示最近 5 条，下拉加载更早记录 */
const PROGRESS_PAGE_SIZE = 5
/** 进展记录展示对象：编辑弹窗与详情弹窗共用同一份（同一时间只开一个） */
const detailOpen = ref(false)
const detailTask = ref<TaskItem | null>(null)
const progressItems = ref<TaskProgressItem[]>([])
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
async function fetchProgress(taskId: string, page: number, append = false) {
  progressLoading.value = true
  try {
    const res = await taskApi.progressList(taskId, { page, size: PROGRESS_PAGE_SIZE })
    progressItems.value = append ? [...progressItems.value, ...res.items] : res.items
    progressTotal.value = res.total
    progressPage.value = page
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    progressLoading.value = false
  }
}

function loadMoreProgress() {
  const tid = form.id || detailTask.value?.id
  if (tid) fetchProgress(tid, progressPage.value + 1, true)
}

/** 编辑：打开表单即加载该任务的进展记录（最近 5 条） */
function loadProgressForEdit(taskId: string) {
  resetProgress()
  fetchProgress(taskId, 1)
}

/** 追加一条进展记录：置顶插入 + 同步列表里的最新进展快照 */
async function addProgress() {
  const content = progressInput.value.trim()
  if (!content) {
    app.toast('请填写本次进展内容', 'error')
    return
  }
  progressBusy.value = true
  try {
    const created = await taskApi.progressAdd(form.id, content)
    progressItems.value = [created, ...progressItems.value]
    progressTotal.value += 1
    progressInput.value = ''
    // 列表「进展描述」列同步更新为最新一条
    const t = tasks.value.find((x) => x.id === form.id)
    if (t) t.latestProgress = created.content
    app.toast('已添加进展')
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    progressBusy.value = false
  }
}

/** 详情（只读）：展示编辑内所有信息 + 进展记录时间轴 */
function openDetail(t: TaskItem) {
  detailTask.value = t
  detailOpen.value = true
  resetProgress()
  fetchProgress(t.id, 1)
}

function countBy(level: string) {
  return tasks.value.filter((t) => t.statusLevel === level).length
}
function progressBar(t: TaskItem) {
  if (t.statusLevel === 'overdue' || t.statusLevel === 'risk') return 'bg-bad-500'
  if (t.statusLevel === 'due_soon') return 'bg-warn-500'
  if (t.statusLevel === 'done') return 'bg-good-500'
  return 'bg-brand-500'
}
const download = downloadFile

async function load() {
  loading.value = true
  try {
    // 平铺视图走后端分页（只取当前页）；分组视图需要全量才能做「每组独立分页」
    const res = await taskApi.list({
      keyword: keyword.value,
      dept_id: deptFilter.value,
      status: statusFilter.value,
      page: groupByDept.value ? 1 : page.value,
      size: groupByDept.value ? GROUP_FETCH_SIZE : PAGE_SIZE,
    })
    tasks.value = res.items
    total.value = res.total
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    loading.value = false
  }
}

/** 条件变更（查询 / 回车 / 切换视图）：回到第一页再查 */
function applyFilters() {
  page.value = 1
  for (const k of Object.keys(groupPages)) delete groupPages[k]
  load()
}

function goPage(n: number) {
  const next = Math.min(Math.max(1, n), pageCount.value)
  if (next === page.value) return
  page.value = next
  load()
}

function setGroupPage(deptId: string, n: number) {
  groupPages[deptId] = Math.max(1, n)
}

/** 切换视图：两种模式的取数方式不同（平铺按页取 / 分组取全量），需重新加载 */
function switchView(grouped: boolean) {
  if (groupByDept.value === grouped) return
  groupByDept.value = grouped
  applyFilters()
}

function openForm(t?: TaskItem) {
  formError.value = ''
  if (t) {
    Object.assign(form, {
      id: t.id,
      parent: t.parent,
      mainTaskId: t.mainTaskId || defaultMainTaskId(),
      description: t.description,
      abnormal: t.abnormal,
      target: Number(t.target),
      done: Number(t.done),
      unit: t.unit,
      note: t.note,
      startDate: t.startDate,
      endDate: t.endDate,
      deptId: t.deptId,
      owner: t.owner,
    })
  } else {
    Object.assign(form, {
      id: '',
      parent: '',
      mainTaskId: defaultMainTaskId(),
      description: '',
      abnormal: false,
      target: 1,
      done: 0,
      unit: '',
      note: '',
      startDate: new Date().toISOString().slice(0, 10),
      endDate: '',
      deptId: orgs.value[1]?.id ?? 'CO',
      owner: owners.value[0]?.name ?? '',
    })
  }
  // 编辑模式加载进展记录（新建无需）
  if (t) loadProgressForEdit(t.id)
  else resetProgress()
  formOpen.value = true
}

async function save() {
  formError.value = ''
  if (!form.parent) return (formError.value = '任务名称不能为空')
  if (!(form.target > 0)) return (formError.value = '目标必须为正数')
  if (!form.endDate) return (formError.value = '请选择计划结束日期')
  if (form.endDate < form.startDate) return (formError.value = '计划结束日期不能早于开始日期')
  if (!form.description.trim()) return (formError.value = '任务描述不能为空')
  // 进展描述必填（新建时填写，成为第一条进展记录；编辑时改为「新增进展」追加）
  if (!form.id && !form.note.trim()) return (formError.value = '进展描述不能为空')

  saving.value = true
  // 请求体使用后端约定的 snake_case 字段（见 docs/design.md §6.5）
  const payload: Record<string, unknown> = {
    parent: form.parent,
    main_task_id: form.mainTaskId || null,
    description: form.description,
    abnormal: form.abnormal,
    target: form.target,
    done: form.done,
    unit: form.unit,
    start_date: form.startDate,
    end_date: form.endDate,
    dept_id: form.deptId,
    owner: form.owner,
  }
  if (!form.id) payload.note = form.note // 仅创建携带进展描述；编辑不可直接改进展
  try {
    if (form.id) await taskApi.update(form.id, payload)
    else await taskApi.create(payload)
    app.toast('保存成功')
    formOpen.value = false
    await load()
  } catch (e) {
    formError.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

/** 新增主任务：调接口创建，刷新下拉并自动选中 */
async function confirmAddMainTask() {
  const name = newMainTaskName.value.trim()
  if (!name) {
    formError.value = '主任务名称不能为空'
    return
  }
  addingMainTaskBusy.value = true
  try {
    const created = await mainTaskApi.create(name)
    mainTasks.value = [...mainTasks.value, created].sort((a, b) => Number(b.isSystem) - Number(a.isSystem) || a.name.localeCompare(b.name))
    form.mainTaskId = created.id
    newMainTaskName.value = ''
    addingMainTask.value = false
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    addingMainTaskBusy.value = false
  }
}

function confirmDelete(t: TaskItem) {
  deleteTarget.value = t
}

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    await taskApi.remove(deleteTarget.value.id)
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
    importResult.value = await taskApi.importFile(file)
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

onMounted(async () => {
  try {
    const [orgsRes, ownersRes, mtRes] = await Promise.all([metaApi.orgs(), metaApi.owners(), mainTaskApi.list()])
    orgs.value = orgsRes
    owners.value = ownersRes
    mainTasks.value = mtRes.sort(
      (a, b) => Number(b.isSystem) - Number(a.isSystem) || a.name.localeCompare(b.name, 'zh'),
    )
  } catch {
    /* 忽略字典加载失败 */
  }
  await load()
})
</script>
