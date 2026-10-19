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
        <button class="btn-ghost" @click="onExportTask">导出</button>
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
        <table :class="rowHeightClass" class="table-freeze table-fixed w-[2109px]">
          <thead>
            <tr class="border-b border-slate-200">
              <th class="th col-id w-[96px]">任务ID</th>
              <th class="th col-maintask w-[213px]">任务组</th>
              <th class="th col-name w-[213px]">任务名称</th>
              <th class="th w-[307px]">任务进展</th>
              <th class="th w-[100px] text-right">目标</th>
              <th class="th w-[110px] text-right">已完成</th>
              <th class="th w-[130px]">完成进度</th>
              <th class="th w-[100px]">责任人</th>
              <th class="th w-[120px]">责任部门</th>
              <th class="th w-[180px]">计划起止</th>
              <th class="th w-[100px]">创建人</th>
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
                  <div class="cell-c text-slate-500" :title="row.task.taskGroupName || '空'">{{ row.task.taskGroupName || '空' }}</div>
                </td>
                <td class="td col-name w-[213px]">
                  <div class="cell-c font-semibold text-slate-800" :title="row.task.parent">{{ row.task.parent }}</div>
                </td>
                <td class="td w-[307px]">
                  <div class="cell-c text-slate-600" :title="row.task.latestProgress || '—'">{{ row.task.latestProgress || '—' }}</div>
                </td>
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
                <td class="td">{{ row.task.owner }}</td>
                <td class="td">{{ row.task.deptName }}</td>
                <td class="td text-xs text-slate-500">{{ row.task.startDate }} ~ {{ row.task.endDate }}</td>
                <td class="td text-slate-500">{{ row.task.createdByName || '—' }}</td>
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
          <label class="label">任务名称<span class="req">*</span><span class="text-slate-400 font-normal">（≤40字）</span></label>
          <input v-model.trim="form.parent" class="input" maxlength="40" placeholder="如：完成全年营收目标 10.2 亿" />
        </div>
        <div>
          <label class="label">任务组<span class="req">*</span><span class="text-slate-400 font-normal">（相关任务可设置归属于同一个任务组，便于集中跟踪；不选则归为「空」）</span></label>
          <div v-if="addingTaskGroup" class="flex items-center gap-2">
            <input
              v-model.trim="newTaskGroupName"
              class="input"
              maxlength="25"
              placeholder="输入新任务组名称（最多 25 字）"
              @keyup.enter="confirmAddTaskGroup"
            />
            <button class="btn-ghost" :disabled="addingTaskGroupBusy" @click="confirmAddTaskGroup">
              {{ addingTaskGroupBusy ? '创建中…' : '确定' }}
            </button>
            <button class="btn-ghost" @click="addingTaskGroup = false">取消</button>
          </div>
          <div v-else class="flex items-center gap-2">
            <div class="relative flex-1 min-w-0">
              <button
                type="button"
                class="input flex items-center justify-between w-full text-left"
                @click="toggleTgDropdown"
              >
                <span class="truncate">{{ selectedTaskGroupLabel || '请选择任务组' }}</span>
                <span class="text-slate-400 ml-2">▾</span>
              </button>
              <!-- 点击空白处关闭下拉 -->
              <div v-if="tgDropdownOpen" class="fixed inset-0 z-10" @click="tgDropdownOpen = false" />
              <!-- 下拉面板：搜索框 + 可滚动列表（下滑到底无限加载更多） -->
              <div
                v-if="tgDropdownOpen"
                class="absolute z-20 mt-1 w-80 rounded-lg border border-slate-200 bg-white shadow-lg"
              >
                <div class="p-2 border-b border-slate-100">
                  <input
                    v-model="tgKeyword"
                    class="input !py-1.5 text-sm"
                    placeholder="搜索任务组（如 华东、营收）"
                    @input="onTgSearch"
                  />
                </div>
                <div class="max-h-60 overflow-auto" @scroll="onTgScroll">
                  <button
                    v-for="m in taskGroups"
                    :key="m.id"
                    type="button"
                    class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-slate-50"
                    :class="form.taskGroupId === m.id ? 'bg-brand-50' : ''"
                    @click="selectTaskGroup(m.id)"
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
                        <!-- 展示任务组责任人（新建时选定 / 首次关联任务回填）；创建人仅存数据表不在此体现 -->
                        <span v-if="m.ownerName" class="text-slate-400 text-xs"> {{ m.ownerName }}</span>
                      </template>
                    </span>
                    <span v-if="renamingId === m.id" class="flex items-center gap-1 shrink-0" @click.stop>
                      <button type="button" class="text-good-600 text-xs" :disabled="renamingBusy" @click="confirmRename(m)">保存</button>
                      <button type="button" class="text-slate-400 text-xs" :disabled="renamingBusy" @click="cancelRename">取消</button>
                    </span>
                    <template v-else>
                      <button
                        v-if="auth.hasPerm('task.edit') && !m.isSystem"
                        type="button"
                        class="text-brand-600 hover:underline text-xs shrink-0"
                        @click.stop="startRename(m)"
                      >
                        编辑
                      </button>
                      <button
                        v-if="auth.hasPerm('task.edit') && !m.isSystem"
                        type="button"
                        class="text-bad-600 hover:underline text-xs shrink-0"
                        @click.stop="startDeleteTaskGroup(m)"
                      >
                        删除
                      </button>
                    </template>
                  </button>
                  <div v-if="tgLoading" class="px-3 py-2 text-xs text-slate-400 text-center">加载中…</div>
                  <div v-else-if="!tgHasMore && taskGroups.length" class="px-3 py-2 text-xs text-slate-300 text-center">没有更多了</div>
                  <div v-else-if="!taskGroups.length && !tgLoading" class="px-3 py-2 text-xs text-slate-300 text-center">无匹配任务组</div>
                </div>
              </div>
            </div>
            <!-- 新增任务组：常显在下拉选择框右侧 -->
            <button v-if="auth.hasPerm('task.edit')" class="btn-ghost whitespace-nowrap shrink-0" @click="addingTaskGroup = true">
              + 新增
            </button>
          </div>
        </div>
        <div>
          <label class="label">责任人<span class="req">*</span><span class="text-slate-400 font-normal">（带所属部门，与账号管理实时联动）</span></label>
          <select v-model="form.owner" class="input" @change="onOwnerChange">
            <option v-for="o in owners" :key="o.id" :value="o.name">{{ o.name }}（{{ o.deptName }}）</option>
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
          <label class="label">任务描述<span class="req">*</span><span class="text-slate-400 font-normal">（≤150字）</span></label>
          <textarea v-model="form.description" rows="2" class="input" maxlength="150" placeholder="任务的背景、交付要求与关键说明" />
        </div>
        <!-- 任务进展：新建时直接填写（必填，成为第一条进展记录）；编辑时只读，通过「新增进展」追加 -->
        <div v-if="!form.id" class="md:col-span-2">
          <label class="label">任务进展<span class="req">*</span><span class="text-slate-400 font-normal">（将作为第一条进展记录，≤150字）</span></label>
          <textarea v-model="form.note" rows="2" class="input" maxlength="150" placeholder="当前进展说明" />
        </div>
        <div v-else class="md:col-span-2">
          <label class="label">任务进展<span class="text-slate-400 font-normal">（不可直接修改，点击「新增进展」追加本次内容）</span></label>
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
          <label class="label">任务组</label>
          <p class="text-sm text-slate-700">{{ detailTask.taskGroupName || '空' }}</p>
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
          <label class="label">任务进展（最近 {{ PROGRESS_PAGE_SIZE }} 条，倒序）</label>
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

<!-- 删除任务组确认 -->
<ModalDialog :open="!!deleteTaskGroupTarget" title="确认删除任务组" width="sm" @close="deleteTaskGroupTarget = null">
  <p class="text-sm text-slate-600">
    将删除任务组「{{ deleteTaskGroupTarget?.name }}」（{{ deleteTaskGroupTarget?.ownerName ? '责任人 ' + deleteTaskGroupTarget?.ownerName : '无责任人' }}）。
    该任务组下已有的任务将自动归到「空」，任务本身不会被删除。此操作不可撤销。
  </p>
  <template #footer>
    <button class="btn-ghost" @click="deleteTaskGroupTarget = null">取消</button>
    <button class="btn-danger" @click="confirmDeleteTaskGroup">确认删除</button>
  </template>
</ModalDialog>

    <!-- 批量导入（含下载模板 + 上传 + 结果） -->
    <ModalDialog :open="importOpen" title="批量导入" width="lg" @close="importOpen = false">
      <div class="space-y-4">
        <p class="text-sm text-slate-500">
          先下载标准模板，在「任务组」列填写名称即可；若该任务组不存在，上传后会自动创建。填好后上传文件完成批量导入。
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
import { useRouter } from 'vue-router'

import { downloadFile, taskGroupApi, metaApi, taskApi } from '@/api'
import ModalDialog from '@/components/ModalDialog.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import type { ImportResult, TaskGroup, TaskItem, TaskProgressItem } from '@/types'
import { fmt } from '@/utils/format'

/** 系统默认任务组 ID（与后端 TG_NONE 约定一致）：任务未选任务组时默认关联它 */
const TG_NONE_ID = 'TG_NONE'

const auth = useAuthStore()
const app = useAppStore()
const router = useRouter()

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
const owners = ref<{ id: string; name: string; deptId?: string; deptName?: string }[]>([])
/** 任务组（原任务分类）下拉选项 */
const taskGroups = ref<TaskGroup[]>([])
/** 新增任务组内联输入 */
const addingTaskGroup = ref(false)
const addingTaskGroupBusy = ref(false)
const newTaskGroupName = ref('')
/** 任务组自定义下拉：展开状态 + 内联改名 */
const tgDropdownOpen = ref(false)
const renamingId = ref('')
const renameValue = ref('')
const renamingBusy = ref(false)

/** 任务组下拉：搜索 + 分页（无限滚动）。默认按权限取最新 10 条，下滑续拉 10 条，关键字为正则匹配。 */
const tgPage = ref(1)
const tgKeyword = ref('')
const tgLoading = ref(false)
const tgHasMore = ref(false)
let tgSearchTimer: ReturnType<typeof setTimeout> | undefined

async function loadTgGroups(reset = false) {
  if (tgLoading.value) return
  if (reset) tgPage.value = 1
  tgLoading.value = true
  try {
    const params: { page: number; size: number; keyword?: string } = { page: tgPage.value, size: 10 }
    const kw = tgKeyword.value.trim()
    if (kw) params.keyword = kw
    const items = await taskGroupApi.list(params)
    taskGroups.value = reset ? items : [...taskGroups.value, ...items]
    tgHasMore.value = items.length === 10
    if (!reset) tgPage.value += 1
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    tgLoading.value = false
  }
}

/** 搜索输入：300ms 防抖后重新拉取第一页 */
function onTgSearch() {
  if (tgSearchTimer) clearTimeout(tgSearchTimer)
  tgSearchTimer = setTimeout(() => loadTgGroups(true), 300)
}

/** 列表滚动到底部时续拉下一页 */
function onTgScroll(e: Event) {
  const el = e.target as HTMLElement
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 8 && tgHasMore.value && !tgLoading.value) {
    loadTgGroups(false)
  }
}

function toggleTgDropdown() {
  tgDropdownOpen.value = !tgDropdownOpen.value
  if (tgDropdownOpen.value && taskGroups.value.length === 0) loadTgGroups(true)
}

/** 确保已选任务组（可能不在当前下拉列表内，如较早创建的任务）可解析出标签 */
async function resolveSelectedTg() {
  const id = form.taskGroupId
  if (!id) {
    selectedTg.value = null
    return
  }
  let found = taskGroups.value.find((x) => x.id === id) ?? null
  if (!found) {
    try {
      found = await taskGroupApi.get(id)
    } catch {
      found = null
    }
    if (found) taskGroups.value = [found, ...taskGroups.value.filter((x) => x.id !== id)]
  }
  selectedTg.value = found
}

/** 当前选中任务组的展示文案：名称 + 责任人（如「注册新公司 胡国海」），系统默认「空」标记。
 *  按需求展示任务组责任人（回填字段）；创建人仅存数据表，不在前端体现。 */
/** 当前选中的任务组对象（用于标签展示，避免懒加载下列表未包含已选项时标签丢失） */
const selectedTg = ref<TaskGroup | null>(null)
const selectedTaskGroupLabel = computed(() => {
  const m = selectedTg.value
  if (!m) return ''
  return `${m.name}${m.isSystem ? '（默认）' : ''}${m.ownerName ? ` ${m.ownerName}` : ''}`
})

function selectTaskGroup(id: string) {
  form.taskGroupId = id
  selectedTg.value = taskGroups.value.find((x) => x.id === id) ?? null
  tgDropdownOpen.value = false
}

function startRename(m: TaskGroup) {
  renamingId.value = m.id
  renameValue.value = m.name
}
function cancelRename() {
  renamingId.value = ''
  renameValue.value = ''
}
async function confirmRename(m: TaskGroup) {
  const name = renameValue.value.trim()
  if (!name) {
    app.toast('任务组名称不能为空', 'error')
    return
  }
  renamingBusy.value = true
  try {
    const updated = await taskGroupApi.rename(m.id, name)
    const idx = taskGroups.value.findIndex((x) => x.id === m.id)
    if (idx >= 0) taskGroups.value[idx] = { ...taskGroups.value[idx], ...updated }
    if (selectedTg.value?.id === m.id) selectedTg.value = { ...selectedTg.value, ...updated }
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
    // 分组视图排序：部门内 → 任务组（按不可变 taskGroupId 归类，同一任务组跨人员排在一起，无任务组 TG_NONE 置后）
    //   → 创建时间倒序（同任务组内新任务在上）。
    // 关键点：任务组优先于人员 —— 同一任务组下的任务必须相邻（如 T20260016 与 T202601 同属
    // 「华东大区营收达成」，即使责任人不相同也要排在一起）；人员维度不再参与排序。
    const sorted = [...items].sort((a, b) => {
      const ae = a.taskGroupId === TG_NONE_ID ? 1 : 0
      const be = b.taskGroupId === TG_NONE_ID ? 1 : 0
      if (ae !== be) return ae - be
      if (a.taskGroupId !== b.taskGroupId) return (a.taskGroupId || '') < (b.taskGroupId || '') ? -1 : 1
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
const COL_COUNT = 14

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
  taskGroupId: '',
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

/** 系统默认任务组 ID（用于新建任务未选任务组时回填） */
function defaultTaskGroupId(): string {
  return taskGroups.value.find((m) => m.isSystem)?.id ?? TG_NONE_ID
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
    // 列表「任务进展」列同步更新为最新一条
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

async function onExportTask() {
  try {
    await taskApi.exportCreate()
    app.toast('已生成导出记录，请前往「下载中心」下载')
    router.push('/downloads')
  } catch (e) {
    app.toast((e as Error).message, 'error')
  }
}

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

async function openForm(t?: TaskItem) {
  formError.value = ''
  if (t) {
    Object.assign(form, {
      id: t.id,
      parent: t.parent,
      taskGroupId: t.taskGroupId || defaultTaskGroupId(),
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
    // 编辑时任务的责任人可能不在当前用户数据权限范围内（下拉未列出），需补入下拉以保证选中项不丢失
    if (t.owner && !owners.value.some((o) => o.name === t.owner)) {
      const dept = orgs.value.find((o) => o.id === t.deptId)
      owners.value = [...owners.value, { id: t.ownerId || '', name: t.owner, deptId: t.deptId, deptName: dept?.name }]
    }
  } else {
    // 责任人默认等于当前操作人（创建人）；可选范围由后端按数据权限过滤（本人/本部门/全公司）
    const ownerName = auth.user?.name ?? owners.value[0]?.name ?? ''
    const ownerObj = owners.value.find((o) => o.name === ownerName)
    Object.assign(form, {
      id: '',
      parent: '',
      taskGroupId: defaultTaskGroupId(),
      description: '',
      abnormal: false,
      target: 1,
      done: 0,
      unit: '',
      note: '',
      startDate: new Date().toISOString().slice(0, 10),
      endDate: '',
      // 责任部门由选中的责任人自动带出（与账号管理实时联动）
      owner: ownerName,
      deptId: ownerObj?.deptId ?? '',
    })
  }
  // 解析已选任务组标签（编辑模式下所选任务组可能不在当前下拉列表内，按需按 ID 拉取）
  await resolveSelectedTg()
  // 编辑模式加载进展记录（新建无需）
  if (t) loadProgressForEdit(t.id)
  else resetProgress()
  formOpen.value = true
}

/** 选中责任人后，自动带出其所属部门（责任部门无需手填，与账号管理实时联动） */
function onOwnerChange() {
  const o = owners.value.find((x) => x.name === form.owner)
  form.deptId = o?.deptId ?? ''
}

async function save() {
  formError.value = ''
  if (!form.parent) return (formError.value = '任务名称不能为空')
  if (form.parent.length > 40) return (formError.value = '任务名称不能超过 40 个字')
  if (form.description.length > 150) return (formError.value = '任务描述不能超过 150 个字')
  if (!form.id && form.note.length > 150) return (formError.value = '任务进展不能超过 150 个字')
  if (!(form.target > 0)) return (formError.value = '目标必须为正数')
  if (!form.endDate) return (formError.value = '请选择计划结束日期')
  if (form.endDate < form.startDate) return (formError.value = '计划结束日期不能早于开始日期')
  if (!form.description.trim()) return (formError.value = '任务描述不能为空')
  // 任务进展必填（新建时填写，成为第一条进展记录；编辑时改为「新增进展」追加）
  if (!form.id && !form.note.trim()) return (formError.value = '任务进展不能为空')

  saving.value = true
  // 请求体使用后端约定的 snake_case 字段（见 docs/design.md §6.5）
  const payload: Record<string, unknown> = {
    parent: form.parent,
    task_group_id: form.taskGroupId || null,
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
  if (!form.id) payload.note = form.note // 仅创建携带任务进展；编辑不可直接改进展
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

/** 新增任务组：调接口创建，刷新下拉并自动选中。
 *  任务组「所属责任人」取当前任务创建界面选中的责任人（form.owner 解析为 user id）。 */
async function confirmAddTaskGroup() {
  const name = newTaskGroupName.value.trim()
  if (!name) {
    formError.value = '任务组名称不能为空'
    return
  }
  if (name.length > 25) {
    formError.value = '任务组名称不能超过 25 个字'
    return
  }
  addingTaskGroupBusy.value = true
  try {
    const ownerObj = owners.value.find((o) => o.name === form.owner)
    const ownerId = ownerObj?.id ?? null
    const created = await taskGroupApi.create(name, ownerId)
    taskGroups.value = [created, ...taskGroups.value.filter((x) => x.id !== created.id)]
    selectedTg.value = created
    form.taskGroupId = created.id
    newTaskGroupName.value = ''
    addingTaskGroup.value = false
  } catch (e) {
    app.toast((e as Error).message, 'error')
  } finally {
    addingTaskGroupBusy.value = false
  }
}

/** 删除任务组：弹确认框；系统默认「空」不可删（后端也会拦截）。 */
const deleteTaskGroupTarget = ref<TaskGroup | null>(null)
function startDeleteTaskGroup(m: TaskGroup) {
  if (m.isSystem) {
    app.toast('系统默认任务组不可删除', 'error')
    return
  }
  deleteTaskGroupTarget.value = m
}
async function confirmDeleteTaskGroup() {
  const m = deleteTaskGroupTarget.value
  if (!m) return
  try {
    await taskGroupApi.remove(m.id)
    taskGroups.value = taskGroups.value.filter((x) => x.id !== m.id)
    // 若当前选中的正是被删任务组，回退到默认「空」
    if (form.taskGroupId === m.id) {
      const def = taskGroups.value.find((x) => x.isSystem) ?? null
      form.taskGroupId = def?.id ?? TG_NONE_ID
      selectedTg.value = def
    }
    app.toast('已删除任务组')
    deleteTaskGroupTarget.value = null
  } catch (e) {
    app.toast((e as Error).message, 'error')
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
    const [orgsRes, ownersRes, mtRes] = await Promise.all([
      metaApi.orgs(),
      metaApi.owners(),
      taskGroupApi.list({ page: 1, size: 10 }),
    ])
    orgs.value = orgsRes
    owners.value = ownersRes
    // 任务组下拉默认加载「最新 10 条」（后端按权限过滤 + 创建时间倒序）；搜索/滚动在服务端分页
    taskGroups.value = mtRes
  } catch {
    /* 忽略字典加载失败 */
  }
  await load()
})
</script>
