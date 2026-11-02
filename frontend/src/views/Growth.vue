<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, RadarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getHistory, getTrend, getLearningPlans, toggleLearningTask } from '@/api/growth'
import { deleteSession } from '@/api/interview'

use([LineChart, RadarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const router = useRouter()

// 页面默认只展示最近几条，其余点「查看全部」再看 —— 记录本身全都在后台存着
const HISTORY_PREVIEW = 5
const PLAN_PREVIEW = 3

const history = ref<any[]>([])
const trend = ref<any>(null)
const plans = ref<any[]>([])
const showAllHistory = ref(false)
const showAllPlans = ref(false)

const expandedPlanIds = ref<Set<number>>(new Set())
const togglingTasks = ref<Set<number>>(new Set())

const PLAN_COLORS = ['#FF8E7B', '#B49EE8', '#3CCDB6', '#6baeea', '#F2A0B6']

const chartReady = computed(() => (trend.value?.dates?.length || 0) > 0)
const radarReady = computed(() => (trend.value?.dimensions?.length || 0) > 0)

const historyShown = computed(() =>
  showAllHistory.value ? history.value : history.value.slice(0, HISTORY_PREVIEW)
)
const plansShown = computed(() =>
  showAllPlans.value ? plans.value : plans.value.slice(0, PLAN_PREVIEW)
)

// ---- 总分趋势 ----
const lineOption = computed(() => {
  const t = trend.value || {}
  const points = t.points || []
  return {
    tooltip: {
      trigger: 'axis',
      // 折线图默认带十字准线，鼠标移到哪一场一目了然
      axisPointer: { type: 'line', lineStyle: { color: 'rgba(255,142,123,0.5)' } },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const pt = points[p.dataIndex] || {}
        const when = [pt.date, pt.time].filter(Boolean).join(' ')
        return `${when}<br/>总分：${p.value == null ? '未评分' : p.value}`
      }
    },
    // bottom 留够两行标签的高度，否则日期/时间会被裁掉
    grid: { left: 46, right: 20, top: 20, bottom: 48 },
    xAxis: {
      type: 'category',
      data: t.dates || [],
      axisLine: { lineStyle: { color: '#d0c5e0' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#82789a',
        fontSize: 11,
        lineHeight: 14,   // 两行标签的行高
        margin: 10,
        hideOverlap: true // 点太密时自动少显示几个，避免糊成一团
      }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLine: { lineStyle: { color: '#d0c5e0' } },
      axisLabel: { color: '#82789a', fontSize: 12 },
      splitLine: { lineStyle: { color: 'rgba(140,110,170,0.1)' } }
    },
    series: [
      {
        name: '总分',
        type: 'line',
        data: t.scores || [],
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        connectNulls: true,
        lineStyle: { width: 3, color: '#FF8E7B' },
        itemStyle: { color: '#FF8E7B' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(255,142,123,0.35)' },
              { offset: 1, color: 'rgba(255,142,123,0.02)' }
            ]
          }
        }
      }
    ]
  }
})

// ---- 能力对比：最近一次 vs 历次平均 ----
const deltaText = computed(() => {
  const l = trend.value?.latest_score
  const a = trend.value?.avg_score
  if (l == null || a == null) return ''
  const d = Math.round((l - a) * 10) / 10
  if (d > 0) return `比平时高 ${d} 分`
  if (d < 0) return `比平时低 ${Math.abs(d)} 分`
  return '与平时持平'
})

const compareRadarOption = computed(() => {
  const dims = trend.value?.dimensions || []
  return {
    tooltip: { trigger: 'item' },
    legend: {
      data: ['最近一次', '历次平均'],
      bottom: 0,
      textStyle: { color: '#82789a', fontSize: 12 }
    },
    radar: {
      indicator: dims.map((d: any) => ({
        name: d.dimension_name || d.dimension_code,
        max: 100
      })),
      shape: 'polygon',
      radius: '62%',
      axisName: { color: '#5c5070', fontSize: 13 },
      splitArea: {
        areaStyle: { color: ['rgba(140,110,170,0.03)', 'rgba(140,110,170,0.06)'] }
      },
      splitLine: { lineStyle: { color: 'rgba(140,110,170,0.15)' } },
      axisLine: { lineStyle: { color: 'rgba(140,110,170,0.15)' } }
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: dims.map((d: any) => d.latest_score ?? 0),
            name: '最近一次',
            areaStyle: { color: 'rgba(255,142,123,0.25)' },
            lineStyle: { width: 2, color: '#FF8E7B' },
            itemStyle: { color: '#FF8E7B' }
          },
          {
            value: dims.map((d: any) => d.avg_score ?? 0),
            name: '历次平均',
            areaStyle: { color: 'rgba(180,158,232,0.12)' },
            lineStyle: { width: 2, type: 'dashed', color: '#B49EE8' },
            itemStyle: { color: '#B49EE8' }
          }
        ]
      }
    ]
  }
})

// ---- 表格 ----
function formatDate(d: string | null | undefined): string {
  if (!d) return '—'
  return d.slice(5, 16).replace('T', ' ')
}

// 后端统一给秒，格式在这里定
function formatDuration(sec: number | null | undefined): string {
  if (sec == null || sec <= 0) return '—'
  const m = Math.floor(sec / 60)
  if (m < 1) return `${sec} 秒`
  if (m < 60) return `${m} 分`
  return `${Math.floor(m / 60)} 小时 ${m % 60} 分`
}

function focusText(r: any): string {
  const dirs = (r.direction_names || []).join('、')
  const pos = r.position_name || ''
  if (dirs && pos) return `${dirs} · ${pos}`
  return dirs || pos || '—'
}

function scoreCell(r: any) {
  if (r.total_score == null) {
    return h('span', { style: { color: '#a79fbb' } }, '未评分')
  }
  const parts: any[] = [
    h('span', { style: { color: '#FF8E7B', fontWeight: 700 } }, Number(r.total_score).toFixed(1))
  ]
  if (r.generated_by === 'RULE') {
    parts.push(h('span', { class: 'rule-tag', title: 'AI 当时不可用，这份分数是本地规则估算的' }, '规则'))
  }
  return h('div', { class: 'score-cell' }, parts)
}

const tableColumns = computed(() => [
  {
    title: '时间',
    dataIndex: 'date',
    key: 'date',
    width: 110,
    customRender: ({ text }: any) => formatDate(text)
  },
  { title: '练习模式', dataIndex: 'mode_name', key: 'mode_name', width: 120 },
  {
    title: '方向 / 岗位',
    key: 'focus',
    customRender: ({ record }: any) => focusText(record)
  },
  {
    title: '题数',
    dataIndex: 'question_count',
    key: 'question_count',
    width: 76,
    customRender: ({ text }: any) => (text ? `${text} 题` : '—')
  },
  {
    title: '评分',
    dataIndex: 'total_score',
    key: 'total_score',
    width: 110,
    customRender: ({ record }: any) => scoreCell(record)
  },
  {
    title: '用时',
    dataIndex: 'actual_duration_sec',
    key: 'duration',
    width: 96,
    customRender: ({ text }: any) => formatDuration(text)
  },
  {
    title: '操作',
    key: 'action',
    width: 132,
    customRender: ({ record }: any) =>
      h('div', { class: 'row-actions' }, [
        h('a', {
          style: { color: '#FF8E7B', cursor: 'pointer', marginRight: '12px' },
          onClick: (e: Event) => { e.stopPropagation(); router.push(`/report/${record.id}`) }
        }, '查看报告'),
        h('a', {
          style: { color: '#d9363e', cursor: 'pointer' },
          onClick: (e: Event) => { e.stopPropagation(); handleDelete(record) }
        }, '删除')
      ])
  }
])

async function handleDelete(row: any) {
  Modal.confirm({
    title: '删除这条面试记录？',
    content: '评估报告、逐题点评会一起删除，不能恢复',
    okText: '删除',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk: async () => {
      await deleteSession(row.id)
      message.success('已删除')
      await load()
    }
  })
}

// ---- 学习计划 ----
function togglePlan(id: number) {
  const s = new Set(expandedPlanIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedPlanIds.value = s
}

async function handleToggleTask(p: any, t: any) {
  if (togglingTasks.value.has(t.id)) return
  togglingTasks.value.add(t.id)
  const prevDone = t.is_done
  const prevStatus = p.status
  // 乐观更新：先改界面，失败再回滚
  t.is_done = !t.is_done
  p.task_done = (p.task_done || 0) + (t.is_done ? 1 : -1)
  p.progress = p.task_total ? Math.round((p.task_done / p.task_total) * 100) : 0
  p.status = p.task_total && p.task_done === p.task_total ? 1 : 0
  try {
    const res = await toggleLearningTask(t.id)
    t.is_done = res.is_done
    p.task_done = res.task_done
    p.progress = res.progress
    p.status = res.plan_status
  } catch {
    t.is_done = prevDone
    p.task_done = (p.task_done || 0) + (t.is_done ? 1 : -1)
    p.progress = p.task_total ? Math.round((p.task_done / p.task_total) * 100) : 0
    p.status = prevStatus
    message.error('打卡失败，请重试')
  } finally {
    togglingTasks.value.delete(t.id)
  }
}

async function load() {
  try { trend.value = await getTrend() } catch { trend.value = null }
  try {
    const list = await getHistory()
    // 只放已完成的（status=2）。没结束的会话既没分数也没用时，
    // 混在"历史面试记录"里只是噪音 —— 挂太久没结束的后端会自动标成已过期。
    history.value = Array.isArray(list) ? list.filter((h: any) => h.status === 2) : []
  } catch {
    history.value = []
  }
  try {
    const list = await getLearningPlans()
    plans.value = Array.isArray(list) ? list : []
  } catch {
    plans.value = []
  }
  // 默认展开最新那份计划
  expandedPlanIds.value = new Set(plans.value.length ? [plans.value[0].id] : [])
}

onMounted(load)
</script>

<template>
  <div class="page-container growth-page">
    <header class="page-head">
      <h2>📈 成长追踪</h2>
      <p class="sub">每面一次，这里就多一条记录</p>
    </header>

    <!-- 总分趋势 -->
    <section class="glass-card sec-card">
      <div class="sec-head">
        <h3 class="sec-title">📈 总分趋势</h3>
        <span v-if="trend?.report_count" class="sec-badge">
          最近 {{ trend.dates.length }} 次 / 共 {{ trend.report_count }} 次
        </span>
      </div>
      <p class="sec-desc">每场面试结束后自动记录总分，折线往上走就是进步</p>
      <v-chart v-if="chartReady" class="chart" :option="lineOption" autoresize />
      <p v-else class="empty-block">
        还没有面试数据。完成一场面试、点「结束面试」后，这里会出现第一个点
      </p>
    </section>

    <!-- 能力对比 -->
    <section class="glass-card sec-card">
      <div class="sec-head">
        <h3 class="sec-title">🎯 能力对比</h3>
      </div>
      <p class="sec-desc">
        实线是你<strong>最近一次</strong>的表现，虚线是你<strong>历次平均</strong>的水平 ——
        两条线离得越远，说明这次离平时越远
      </p>
      <template v-if="radarReady">
        <p class="cmp-line">
          最近一次 <strong>{{ trend.latest_score ?? '—' }}</strong> 分
          <span class="dot">·</span>
          历次平均 <strong>{{ trend.avg_score ?? '—' }}</strong> 分
          <em v-if="deltaText">{{ deltaText }}</em>
        </p>
        <v-chart class="chart small" :option="compareRadarOption" autoresize />
      </template>
      <p v-else class="empty-block">还没有面试数据。面完一场就能看到五个维度的得分</p>
    </section>

    <!-- 历史面试记录 -->
    <section class="glass-card sec-card">
      <div class="sec-head">
        <h3 class="sec-title">📋 历史面试记录</h3>
        <span v-if="history.length" class="sec-badge">共 {{ history.length }} 次</span>
      </div>
      <a-table
        v-if="history.length"
        :columns="tableColumns"
        :data-source="historyShown"
        :pagination="false"
        :bordered="false"
        size="middle"
        row-key="id"
      />
      <p v-else class="empty-block">
        还没有面试记录。去「开始面试」跑一场，结束后面试报告会自动记到这里
      </p>
      <div v-if="history.length > HISTORY_PREVIEW" class="more-bar">
        <a @click="showAllHistory = !showAllHistory">
          {{ showAllHistory ? '收起' : `查看全部 ${history.length} 次` }}
        </a>
      </div>
    </section>

    <!-- 学习计划 -->
    <section class="glass-card sec-card">
      <div class="sec-head">
        <h3 class="sec-title">📚 学习计划</h3>
        <span v-if="plans.length" class="sec-badge">共 {{ plans.length }} 份</span>
      </div>
      <p class="sec-desc">
        每场面试结束后，AI 会按你答得不好的地方安排任务。点任务那一行就能打卡
      </p>

      <div v-if="plans.length" class="ai-plan-list">
        <div
          v-for="(p, i) in plansShown"
          :key="p.id"
          :class="['ai-plan-card', { collapsed: !expandedPlanIds.has(p.id) }]"
        >
          <div class="ai-plan-head clickable" @click="togglePlan(p.id)">
            <span class="ai-plan-title" :style="{ borderColor: PLAN_COLORS[i % PLAN_COLORS.length] }">
              {{ p.title }}
            </span>
            <span v-if="p.start_date" class="ai-plan-dates">{{ p.start_date }} ~ {{ p.end_date }}</span>
            <span class="ai-plan-chevron">{{ expandedPlanIds.has(p.id) ? '▾' : '▸' }}</span>
          </div>

          <template v-if="expandedPlanIds.has(p.id)">
            <p v-if="p.target" class="ai-plan-target">🎯 {{ p.target }}</p>

            <div class="ai-sww">
              <div v-if="p.strengths_text" class="ai-sw strengths">
                <div class="ai-sw-label">✅ 这次做得好的</div>
                <p class="ai-sw-text">{{ p.strengths_text }}</p>
              </div>
              <div v-if="p.weaknesses_text" class="ai-sw weaknesses">
                <div class="ai-sw-label">⚠️ 待提升</div>
                <p class="ai-sw-text">{{ p.weaknesses_text }}</p>
              </div>
            </div>

            <div class="ai-tasks">
              <div class="ai-tasks-head">
                <span>学习任务 {{ p.task_done }}/{{ p.task_total }}</span>
                <span class="plan-pct">{{ p.progress }}%</span>
              </div>
              <a-progress
                :percent="p.progress"
                :show-info="false"
                :stroke-color="PLAN_COLORS[i % PLAN_COLORS.length]"
              />
              <div
                v-for="t in p.tasks"
                :key="t.id"
                :class="['ai-task', { done: t.is_done }]"
                :title="t.is_done ? '点击取消打卡' : '点击完成打卡'"
                @click="handleToggleTask(p, t)"
              >
                <span class="ai-task-check">{{ t.is_done ? '☑' : '☐' }}</span>
                <div class="ai-task-body">
                  <div class="ai-task-title">
                    {{ t.title }} <span class="ai-task-date">{{ t.task_date }}</span>
                  </div>
                  <div v-if="t.content" class="ai-task-content">{{ t.content }}</div>
                </div>
              </div>
            </div>
          </template>

          <div v-else class="ai-plan-brief">
            <a-progress
              :percent="p.progress"
              :show-info="false"
              :stroke-color="PLAN_COLORS[i % PLAN_COLORS.length]"
            />
            <span class="ai-plan-brief-pct">{{ p.task_done }}/{{ p.task_total }} · {{ p.progress }}%</span>
          </div>
        </div>
      </div>
      <p v-else class="empty-block">
        暂无学习计划。完成一场面试后，AI 会根据你的表现自动生成
      </p>

      <div v-if="plans.length > PLAN_PREVIEW" class="more-bar">
        <a @click="showAllPlans = !showAllPlans">
          {{ showAllPlans ? '收起' : `查看全部 ${plans.length} 份` }}
        </a>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* 通用区块样式在 src/styles/index.css，这里只留本页私有部分 */

.chart { height: 300px; }
.chart.small { height: 320px; }

.cmp-line {
  margin: 0 0 4px;
  font-size: 14px;
  color: #82789a;
}
.cmp-line strong { color: #3d3848; font-size: 17px; font-weight: 700; }
.cmp-line .dot { margin: 0 8px; color: #d0c5e0; }
.cmp-line em {
  margin-left: 10px;
  font-style: normal;
  font-size: 12px;
  color: #ff8e7b;
}

.score-cell { display: flex; align-items: center; gap: 6px; }
.rule-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 20px;
  background: rgba(255, 186, 96, 0.18);
  color: #a15c12;
}

.more-bar { margin-top: 14px; text-align: center; }
.more-bar a { color: #ff8e7b; cursor: pointer; font-size: 13px; }
.more-bar a:hover { text-decoration: underline; }

/* 学习计划卡片 */
.ai-plan-list { display: flex; flex-direction: column; gap: 12px; }
.ai-plan-card {
  border: 1px solid rgba(232, 227, 220, 0.8);
  border-radius: 10px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.6);
}
.ai-plan-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ai-plan-head.clickable { cursor: pointer; }
.ai-plan-title {
  font-weight: 600;
  color: #3d3848;
  border-left: 3px solid #ff8e7b;
  padding-left: 8px;
}
.ai-plan-dates { font-size: 12px; color: #a79fbb; }
.ai-plan-chevron { margin-left: auto; color: #a79fbb; }

.ai-plan-target { margin: 10px 0 0; font-size: 13px; color: #6f6685; }

.ai-sww { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.ai-sw { padding: 10px 12px; border-radius: 8px; }
.ai-sw.strengths { background: rgba(60, 205, 182, 0.08); }
.ai-sw.weaknesses { background: rgba(255, 142, 123, 0.08); }
.ai-sw-label { font-size: 12px; font-weight: 600; color: #6f6685; margin-bottom: 4px; }
.ai-sw-text { margin: 0; font-size: 13px; color: #3d3848; line-height: 1.7; white-space: pre-line; }

.ai-tasks { margin-top: 14px; }
.ai-tasks-head {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #82789a;
  margin-bottom: 6px;
}
.plan-pct { color: #ff8e7b; font-weight: 600; }

.ai-task {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  margin-top: 6px;
  border-radius: 8px;
  cursor: pointer;
  background: rgba(140, 110, 170, 0.05);
  transition: background 0.15s;
}
.ai-task:hover { background: rgba(140, 110, 170, 0.1); }
.ai-task.done { opacity: 0.6; }
.ai-task.done .ai-task-title { text-decoration: line-through; }
.ai-task-check { flex: none; color: #3ccdb6; font-size: 15px; line-height: 1.4; }
.ai-task-body { flex: 1; }
.ai-task-title { font-size: 13px; color: #3d3848; font-weight: 500; }
.ai-task-date { font-size: 11px; color: #a79fbb; font-weight: 400; margin-left: 6px; }
.ai-task-content { font-size: 12px; color: #82789a; line-height: 1.6; margin-top: 2px; }

.ai-plan-brief { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.ai-plan-brief-pct { flex: none; font-size: 12px; color: #82789a; }

@media (max-width: 860px) {
  .ai-sww { grid-template-columns: 1fr; }
}
</style>
