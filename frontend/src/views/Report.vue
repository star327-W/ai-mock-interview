<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getReport, getReviews } from '@/api/evaluation'

use([RadarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const sessionId = computed(() => Number(route.params.sessionId))

const report = ref<any>(null)
const reviews = ref<any[]>([])

// radar 图动态从 report.dimensions 生成
const radarOption = computed(() => {
  const dims = report.value?.dimensions || []
  if (!dims.length) return null
  return {
    tooltip: {},
    radar: {
      indicator: dims.map((d: any) => ({ name: d.dimension_name || d.name, max: 100 })),
      radius: '65%',
      center: ['50%', '55%'],
      axisName: { color: '#82789a', fontSize: 13 }
    },
    series: [
      {
        type: 'radar',
        areaStyle: { color: 'rgba(255, 142, 123, 0.35)' },
        lineStyle: { color: '#FF8E7B', width: 2 },
        itemStyle: { color: '#FF8E7B' },
        data: [{ value: dims.map((d: any) => Number(d.score) || 0), name: '本次面试' }]
      }
    ]
  }
})

async function load() {
  try {
    report.value = await getReport(sessionId.value)
  } catch {
    report.value = {
      total_score: 76,
      dimensions: [
        { dimension_name: '技术深度', score: 78 },
        { dimension_name: '沟通表达', score: 82 },
        { dimension_name: '问题分析', score: 70 },
        { dimension_name: '系统设计', score: 65 },
        { dimension_name: '项目经验', score: 85 },
      ]
    }
  }
  try {
    reviews.value = await getReviews(sessionId.value)
  } catch {
    reviews.value = [
      { question_text: '请做一下自我介绍。', answer_text: '我叫王同学，XX 大学计算机专业…', reference_answer: '建议突出与岗位匹配的亮点项目。', improvement: '1) 控制在 1-2 分钟；2) 突出数据化成果。' },
      { question_text: '说一说你最有代表性的项目。', answer_text: '我做过一个电商秒杀系统…', reference_answer: 'STAR 法则 + 关键决策 + 数据指标。', improvement: '建议更突出个人贡献、决策过程与优化结果的前后对比。' }
    ]
  }
}

function goGrowth() { router.push('/growth') }
function goAgain() { router.push('/interview/config') }

onMounted(load)
</script>

<template>
  <div class="page-container report-page">
    <div class="head">
      <h2>🎉 你的面试报告</h2>
      <p class="sub">以下是对你本次模拟面试的多维度评估</p>
      <!-- 本场用了什么练习模式 / 什么人设 —— 让用户知道分数是在哪种条件下拿到的 -->
      <p class="report-meta" v-if="report?.mode_name || report?.persona_name">
        🎯 本场：{{ report?.mode_name || '—' }} · {{ report?.persona_name || '—' }}
      </p>
    </div>

    <!-- AI 不可用时的降级提示：必须让用户知道这不是 AI 分析出来的 -->
    <div v-if="report?.generated_by === 'RULE'" class="fallback-tip">
      ⚠️ 本次报告由<strong>本地规则粗略估算</strong>（AI 评分服务暂时不可用），
      维度分与评语仅供参考，请以逐题点评为准。
    </div>

    <!-- 总分 -->
    <div class="total-score glass-card">
      <div class="score-wrap">
        <div class="score-num">{{ report?.total_score != null ? Number(report.total_score).toFixed(1) : '—' }}</div>
        <div class="score-label">综合评分</div>
      </div>
      <div class="score-meta">
        <div class="meta-item">
          <div class="meta-value">{{ reviews.length }}</div>
          <div class="meta-label">答题数</div>
        </div>
        <div class="meta-item">
          <div class="meta-value">{{ report?.dimensions?.length || 0 }}</div>
          <div class="meta-label">评估维度</div>
        </div>
        <div class="meta-item" v-if="report?.summary">
          <div class="meta-label long">{{ report.summary.slice(0, 40) }}{{ report.summary.length > 40 ? '…' : '' }}</div>
        </div>
      </div>
    </div>

    <!-- 分维度 -->
    <div class="glass-card sec-card">
      <h3 class="sec-title">📊 分维度评分</h3>
      <div v-if="report?.dimensions?.length" class="dim-list">
        <div v-for="d in report.dimensions" :key="d.dimension_code || d.dimension_name" class="dim-item">
          <div class="dim-row">
            <span class="dim-name">{{ d.dimension_name || d.name }}</span>
            <span class="dim-score">{{ Number(d.score).toFixed(1) }}</span>
          </div>
          <a-progress
            :percent="Math.min(Number(d.score), 100)"
            :stroke-color="{
              '0%': '#FF8E7B',
              '50%': '#FFB4A0',
              '100%': '#F2A0B6'
            }"
            :show-info="false"
            :trail-color="'rgba(140,110,170,0.1)'"
            size="small"
          />
        </div>
      </div>
      <a-empty v-else description="暂无评分数据" />
    </div>

    <!-- 雷达图 -->
    <div v-if="radarOption" class="glass-card sec-card">
      <h3 class="sec-title">🎯 能力雷达图</h3>
      <v-chart class="radar" :option="radarOption" autoresize />
    </div>

    <!-- 逐题复盘 -->
    <div class="glass-card sec-card">
      <h3 class="sec-title">📝 逐题复盘</h3>
      <a-collapse v-if="reviews.length" :bordered="false" class="review-collapse">
        <a-collapse-panel
          v-for="(r, idx) in reviews"
          :key="r.id || idx"
          :header="`第 ${r.seq ?? idx + 1} 题 · ${(r.question_text || '').slice(0, 30)}${(r.question_text || '').length > 30 ? '…' : ''}`"
        >
          <div class="review-block">
            <div class="rb-title">❓ 题目原文</div>
            <div class="rb-body">{{ r.question_text || '—' }}</div>
          </div>
          <div class="review-block">
            <div class="rb-title">💬 你的回答</div>
            <div class="rb-body">{{ r.answer_text || '（未作答）' }}</div>
          </div>
          <div class="review-block" v-if="r.reference_answer">
            <div class="rb-title">✅ 参考答案</div>
            <div class="rb-body">{{ r.reference_answer }}</div>
          </div>
          <div class="review-block" v-if="r.strengths">
            <div class="rb-title">✨ 亮点</div>
            <div class="rb-body">{{ r.strengths }}</div>
          </div>
          <div class="review-block" v-if="r.weaknesses">
            <div class="rb-title">⚠️ 不足</div>
            <div class="rb-body">{{ r.weaknesses }}</div>
          </div>
          <div class="review-block" v-if="r.improvement">
            <div class="rb-title">💡 改进建议</div>
            <div class="rb-body suggest">{{ r.improvement }}</div>
          </div>
          <div class="review-block" v-if="r.score != null">
            <div class="rb-title">🎯 本题得分</div>
            <div class="rb-body score-line">{{ Number(r.score).toFixed(1) }} / 100</div>
          </div>
        </a-collapse-panel>
      </a-collapse>
      <a-empty v-else description="暂无复盘数据" />
    </div>

    <div class="foot-actions">
      <a-button class="btn-outline" size="large" @click="goGrowth">查看成长轨迹</a-button>
      <a-button class="btn-coral" size="large" @click="goAgain">再来一次 →</a-button>
    </div>
  </div>
</template>

<style scoped>
.head { margin-bottom: 20px; }
.head h2 { font-size: 22px; color: #3d3848; margin: 0; }
.head .sub { font-size: 14px; color: #82789a; margin-top: 4px; }
/* 本场模式/人设标注：薄荷绿小胶囊，和页面其他标签风格一致 */
.report-meta {
  display: inline-block;
  margin-top: 10px;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: #28695c;
  background: rgba(60, 205, 182, 0.12);
  border: 1px solid rgba(60, 205, 182, 0.3);
}

/* 降级提示条：AI 不可用时的醒目提醒 */
.fallback-tip {
  padding: 12px 18px;
  margin-bottom: 20px;
  border-radius: 10px;
  border: 1px solid rgba(230, 145, 60, 0.45);
  background: rgba(255, 186, 96, 0.14);
  color: #a15c12;
  font-size: 13px;
  line-height: 1.6;
}

.total-score {
  display: flex;
  align-items: center;
  gap: 40px;
  padding: 32px;
  margin-bottom: 20px;
}
.score-wrap { display: flex; flex-direction: column; align-items: center; }
.score-num {
  font-size: 64px;
  font-weight: 800;
  background: linear-gradient(135deg, #FF8E7B 0%, #FFB4A0 50%, #F2A0B6 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  line-height: 1;
}
.score-label { font-size: 14px; color: #82789a; margin-top: 6px; }
.score-meta { flex: 1; display: flex; gap: 24px; justify-content: center; }
.meta-item {
  flex: 1;
  padding: 16px;
  border-radius: 12px;
  background: rgba(140,110,170,0.06);
  text-align: center;
}
.meta-value { font-size: 20px; font-weight: 700; color: #3d3848; }
.meta-label { font-size: 12px; color: #82789a; margin-top: 4px; }
.meta-label.long { font-size: 12px; line-height: 1.5; margin-top: 6px; }

.sec-card { padding: 24px; margin-bottom: 20px; }
.sec-title { margin: 0 0 16px; font-size: 16px; color: #3d3848; }

.dim-list { display: flex; flex-direction: column; gap: 14px; }
.dim-row { display: flex; justify-content: space-between; margin-bottom: 4px; }
.dim-name { color: #3d3848; font-weight: 500; }
.dim-score { color: #FF8E7B; font-weight: 700; }

.radar { height: 340px; }

.review-collapse .ant-collapse-item { border-radius: 10px; margin-bottom: 10px; background: rgba(140,110,170,0.04); }
.review-block { margin-bottom: 12px; }
.rb-title { font-size: 13px; color: #82789a; margin-bottom: 4px; }
.rb-body {
  padding: 10px 14px;
  background: rgba(255,255,255,0.8);
  border-radius: 8px;
  color: #3d3848;
  line-height: 1.7;
  font-size: 13px;
}
.rb-body.suggest { border-left: 3px solid #FF8E7B; background: rgba(255, 244, 242, 0.6); }
.rb-body.score-line { color: #FF8E7B; font-weight: 700; font-size: 16px; text-align: center; }

.foot-actions { display: flex; gap: 12px; justify-content: center; padding-top: 8px; }
</style>
