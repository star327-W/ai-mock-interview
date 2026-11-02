<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Modal, message } from 'ant-design-vue'
import { getSummary } from '@/api/growth'
import { getPosts } from '@/api/community'
import { getMembershipMe } from '@/api/membership'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// 统计卡片点击行为映射（注意：'剩余面试次数' 也包含 '面试次数'，需先匹配剩余次数）
function handleStatClick(s: { label: string }) {
  if (s.label.includes('剩余')) {
    router.push('/membership')
  } else if (s.label.includes('面试次数') || s.label.includes('平均面试评分')) {
    router.push('/growth')
  } else if (s.label.includes('打卡') || s.label.includes('提升幅度')) {
    router.push('/growth')
  }
}

// 欢迎昵称：优先用后端返回的真实昵称，兜底用手机号后4位
const displayName = computed(() => {
  if (userStore.userInfo?.nickname) return userStore.userInfo.nickname
  if (userStore.userInfo?.phone) return `用户${userStore.userInfo.phone.slice(-4)}`
  return '同学'
})

// 统计卡片：初始为空态，接口返回后填充真实数据（打卡记录只在成长追踪页展示）
const stats = ref([
  { icon: '🎤', label: '剩余面试次数', value: 0, unit: '', cls: 'grad-coral' },
  { icon: '📊', label: '平均面试评分', value: '-', unit: '分', cls: 'grad-turquoise' },
  { icon: '📈', label: '本月提升幅度', value: '-', unit: '%', cls: 'grad-honey' },
  { icon: '🗂', label: '累计面试次数', value: 0, unit: '', cls: 'grad-purple' }
])

// 学习计划：来自后端真实数据
const plans = ref<Array<{ name: string; progress: number }>>([])

const recommendations = ref<Array<any>>([])

function goInterview() {
  router.push('/interview/config')
}
function goCommunity(id: number) {
  router.push('/community')
}

const PLAN_COLORS = ['#FF8E7B', '#3CCDB6', '#B49EE8']

onMounted(async () => {
  // 拉取用户信息（如果尚未加载）
  if (!userStore.userInfo) {
    try { await userStore.fetchMe() } catch { /* ignore */ }
  }
  // 首页真实数据概览
  try {
    const summary = await getSummary()
    if (summary) {
      stats.value[1].value = summary.avg_score ?? '-'
      stats.value[2].value = summary.month_improve ?? '-'
      stats.value[3].value = summary.total_interviews ?? 0
      plans.value = Array.isArray(summary.plans) ? summary.plans : []
    }
  } catch { /* 接口异常时保持空态 */ }
  // 剩余面试次数（含会员状态）
  try {
    const me = await getMembershipMe()
    if (me) {
      stats.value[0].value = me.is_demo
        ? '无限'
        : me.membership?.is_active
          ? '不限'
          : (me.free_quota?.remain_count ?? 0)
    }
  } catch { /* 接口异常时保持空态 */ }
  // 推荐面经（取前3条）
  try {
    const posts = await getPosts()
    recommendations.value = Array.isArray(posts) ? posts.slice(0, 3) : []
  } catch { /* 接口异常时保持空态 */ }
})
</script>

<template>
  <div class="page-container">
    <div class="welcome">
      <h1 class="welcome-title">欢迎回来，{{ displayName }} 👋</h1>
      <p class="welcome-sub">今天来一场模拟面试吧，每一次练习都在靠近你的 Offer</p>
    </div>

    <!-- 数据概览 -->
    <div class="stats-row">
      <div v-for="s in stats" :key="s.label" class="stat-card glass-card clickable" @click="handleStatClick(s)">
        <div :class="['stat-head', s.cls]">
          <span class="stat-icon">{{ s.icon }}</span>
          <span class="stat-label">{{ s.label }}</span>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ s.value }}</span>
          <span class="stat-unit">{{ s.unit }}</span>
        </div>
      </div>
    </div>

    <!-- 两列：开始面试 + 学习计划 -->
    <div class="home-row">
      <div class="start-card">
        <div class="start-inner">
          <div class="start-emoji">🎙️</div>
          <h2 class="start-title">开始模拟面试</h2>
          <p class="start-sub">选择练习模式、面试官人设，让 AI 陪你实战一把</p>
          <button class="start-btn" @click="goInterview">立即开始 →</button>
        </div>
      </div>

      <div class="plan-card glass-card">
        <h3 class="plan-title">📚 我的学习计划</h3>
        <div v-if="plans.length" class="plan-list">
          <div v-for="(p, i) in plans" :key="p.name" class="plan-item">
            <div class="plan-head">
              <span>{{ p.name }}</span>
              <span class="plan-pct">{{ p.progress }}%</span>
            </div>
            <a-progress
              :percent="p.progress"
              :stroke-color="PLAN_COLORS[i % PLAN_COLORS.length]"
              :show-info="false"
              :trail-color="'rgba(140,110,170,0.12)'"
            />
          </div>
        </div>
        <div v-else class="plan-empty">暂无学习计划，完成一场面试后会自动生成</div>
      </div>
    </div>

    <!-- 推荐面经 -->
    <div class="section-head">
      <h3>🔥 推荐面经</h3>
      <a class="more" @click="$router.push('/community')">查看全部 →</a>
    </div>
    <div class="reco-row">
      <div v-for="r in recommendations" :key="r.id" class="reco-card glass-card" @click="goCommunity(r.id)">
        <div class="reco-tags">
          <span v-if="r.company_name" class="tag company">{{ r.company_name }}</span>
          <span v-if="r.position_name" class="tag pos">{{ r.position_name }}</span>
        </div>
        <div class="reco-title">{{ r.title }}</div>
        <div class="reco-foot">
          <span>❤️ {{ r.like_count || 0 }}</span>
          <span v-if="r.author" class="reco-author">{{ r.author }}</span>
        </div>
      </div>
      <a-empty v-if="!recommendations.length" description="暂无面经，去社区发布第一篇吧" style="grid-column: 1 / -1; padding: 30px 0;" />
    </div>
  </div>
</template>

<style scoped>
.welcome { margin-bottom: 24px; }
.welcome-title { font-size: 26px; font-weight: 700; color: #3d3848; margin: 0; }
.welcome-sub { font-size: 14px; color: #82789a; margin-top: 6px; }

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card { overflow: hidden; padding: 0; }
.stat-card.clickable { cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
.stat-card.clickable:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(140,110,170,0.18); }
.stat-head {
  padding: 14px 18px;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 13px;
}
.stat-icon { font-size: 20px; }
.stat-body { padding: 18px; display: flex; align-items: baseline; gap: 4px; }
.stat-value { font-size: 34px; font-weight: 700; color: #3d3848; }
.stat-unit { font-size: 14px; color: #82789a; }

.home-row {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 20px;
  margin-bottom: 28px;
}
.start-card {
  border-radius: 16px;
  padding: 32px;
  background: linear-gradient(135deg, #b49ee8 0%, #d4c8f0 50%, #6baeea 100%);
  color: #fff;
  box-shadow: 0 12px 32px rgba(180, 158, 232, 0.35);
  position: relative;
  overflow: hidden;
}
.start-emoji { font-size: 48px; }
.start-title { font-size: 22px; margin: 10px 0 6px; color: #fff; }
.start-sub { font-size: 14px; opacity: 0.92; margin-bottom: 20px; }
.start-btn {
  background: #fff;
  color: #b49ee8;
  border: none;
  padding: 10px 24px;
  border-radius: 24px;
  font-weight: 700;
  font-size: 15px;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(0,0,0,0.12);
  transition: transform 0.15s;
}
.start-btn:hover { transform: translateY(-2px); }

.plan-card { padding: 24px; }
.plan-title { margin: 0 0 18px; font-size: 16px; color: #3d3848; }
.plan-item { margin-bottom: 16px; }
.plan-head { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 13px; color: #3d3848; }
.plan-pct { color: #82789a; }
.plan-empty {
  padding: 28px 0;
  text-align: center;
  font-size: 13px;
  color: #82789a;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.section-head h3 { font-size: 17px; color: #3d3848; margin: 0; }
.section-head .more { font-size: 13px; color: #FF8E7B; cursor: pointer; }

.reco-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.reco-card {
  padding: 18px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.reco-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(140,110,170,0.14); }
.reco-tags { display: flex; gap: 8px; margin-bottom: 10px; }
.tag { font-size: 12px; padding: 2px 10px; border-radius: 10px; }
.tag.company { background: rgba(255,142,123,0.15); color: #FF8E7B; }
.tag.pos { background: rgba(60,205,182,0.15); color: #3CCDB6; }
.reco-title { font-size: 14px; font-weight: 600; color: #3d3848; line-height: 1.5; min-height: 42px; }
.reco-foot { font-size: 12px; color: #82789a; margin-top: 10px; }

@media (max-width: 960px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .home-row { grid-template-columns: 1fr; }
  .reco-row { grid-template-columns: 1fr; }
}
</style>
