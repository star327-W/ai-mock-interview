<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { CrownFilled, CheckOutlined } from '@ant-design/icons-vue'
import {
  getMembershipMe, getPlans, createOrder, getOrders,
  type MembershipPlan, type MembershipMe, type OrderItem
} from '@/api/membership'

const loading = ref(true)
const me = ref<MembershipMe | null>(null)
const plans = ref<MembershipPlan[]>([])
const orders = ref<OrderItem[]>([])

// 收银台
const cashierVisible = ref(false)
const paying = ref(false)
const payType = ref<'WECHAT' | 'ALIPAY'>('WECHAT')
const selectedPlan = ref<MembershipPlan | null>(null)

const remainText = computed(() => {
  if (!me.value) return '-'
  if (me.value.is_demo) return '无限'
  return me.value.membership.is_active ? '不限次' : String(me.value.free_quota.remain_count)
})
const isMember = computed(() => me.value?.membership.is_active ?? false)
const isDemo = computed(() => me.value?.is_demo ?? false)

const STATUS_TEXT: Record<number, string> = { 0: '待支付', 1: '已支付', 2: '已退款', 3: '已关闭' }
function fmtMoney(fen: number) {
  return (fen / 100).toFixed(2).replace(/\.00$/, '')
}
function fmtTime(iso: string | null) {
  if (!iso) return '-'
  return iso.slice(0, 19).replace('T', ' ')
}

function openCashier(p: MembershipPlan) {
  if (!p.purchasable) {
    message.warning('首充特惠仅限新用户购买一次')
    return
  }
  selectedPlan.value = p
  payType.value = 'WECHAT'
  cashierVisible.value = true
}

async function confirmPay() {
  if (!selectedPlan.value) return
  paying.value = true
  try {
    const res = await createOrder(selectedPlan.value.id, payType.value)
    cashierVisible.value = false
    message.success(res?.benefit_msg || '支付成功')
    await loadData() // 刷新次数/会员状态/订单
  } catch { /* request 层已弹错误 */ }
  finally { paying.value = false }
}

async function loadData() {
  loading.value = true
  try {
    const [m, p, o] = await Promise.all([getMembershipMe(), getPlans(), getOrders()])
    me.value = m
    plans.value = p || []
    orders.value = o || []
  } catch { /* 保持空态 */ }
  finally { loading.value = false }
}

onMounted(loadData)
</script>

<template>
  <div class="page-container">
    <div class="membership-header glass-card">
      <div class="mh-left">
        <div class="mh-crown"><CrownFilled /></div>
        <div>
          <h2 class="mh-title">会员中心</h2>
          <p class="mh-sub" v-if="isMember">
            {{ me?.membership.plan_name }} 有效，至 {{ me?.membership.expire_at?.slice(0, 10) }} · 期内不限次面试
          </p>
          <p class="mh-sub" v-else-if="isDemo">演示账号 · 面试次数无限，每次进入自动清空</p>
          <p class="mh-sub" v-else>当前剩余面试次数 <b class="mh-count">{{ remainText }}</b> 次，购买套餐立即解锁完整面试</p>
        </div>
      </div>
      <div class="mh-right" :class="{ member: isMember || isDemo }">
        <div class="mh-num">{{ remainText }}</div>
        <div class="mh-num-label">{{ isDemo ? '演示不限次' : isMember ? '会员不限次' : '剩余次数' }}</div>
      </div>
    </div>

    <h3 class="section-title">充值套餐</h3>
    <div class="plans-grid">
      <div
        v-for="p in plans"
        :key="p.id"
        :class="['plan-card', 'glass-card', { 'plan-disabled': !p.purchasable, 'plan-member': !p.is_time_card }]"
        @click="openCashier(p)"
      >
        <span v-if="p.features?.tag" class="plan-tag">{{ p.features.tag }}</span>
        <div class="plan-name">{{ p.name }}</div>
        <div class="plan-price">
          <span class="price-cur">¥</span>
          <span class="price-num">{{ fmtMoney(p.price_fen) }}</span>
          <span class="price-suffix" v-if="p.duration_days">/ {{ p.duration_days >= 365 ? '年' : p.duration_days >= 90 ? '季' : '月' }}</span>
          <span class="price-suffix" v-else>/ {{ p.interview_quota }} 次</span>
        </div>
        <div class="plan-origin" v-if="p.features?.original_price_fen">
          原价 ¥{{ fmtMoney(p.features.original_price_fen) }}
        </div>
        <ul class="plan-desc">
          <li><CheckOutlined /> {{ p.features?.desc || '完整模拟面试' }}</li>
          <li><CheckOutlined /> AI 逐题评分 + 成长报告</li>
        </ul>
        <div class="plan-cta" :class="{ ok: p.purchasable }">
          {{ p.purchasable ? (p.is_time_card ? '立即购买' : '立即开通') : '已购买' }}
        </div>
      </div>
    </div>

    <h3 class="section-title">充值记录</h3>
    <div class="orders glass-card">
      <a-empty v-if="!loading && orders.length === 0" description="暂无充值记录" />
      <div v-for="o in orders" :key="o.id" class="order-row">
        <div class="order-left">
          <span class="order-name">{{ o.plan_name }}</span>
          <span class="order-no">{{ o.order_no }}</span>
        </div>
        <div class="order-right">
          <span class="order-status" :class="{ paid: o.pay_status === 1 }">{{ STATUS_TEXT[o.pay_status] || '-' }}</span>
          <span class="order-amount">¥{{ fmtMoney(o.amount_fen) }}</span>
          <span class="order-time">{{ fmtTime(o.paid_at || o.created_at) }}</span>
        </div>
      </div>
    </div>

    <!-- 收银台弹窗 -->
    <a-modal v-model:open="cashierVisible" :footer="null" :width="380" centered class="cashier-modal">
      <div class="cashier" v-if="selectedPlan">
        <h3 class="cashier-title">收银台</h3>
        <div class="cashier-plan">{{ selectedPlan.name }}</div>
        <div class="cashier-amount">¥{{ fmtMoney(selectedPlan.price_fen) }}</div>
        <div class="cashier-benefit">
          {{ selectedPlan.is_time_card ? `到账 ${selectedPlan.interview_quota} 次，永不过期` : '开通后会员期内不限次面试' }}
        </div>
        <div class="pay-methods">
          <div :class="['pay-method', { active: payType === 'WECHAT' }]" @click="payType = 'WECHAT'">
            💚 微信支付
          </div>
          <div :class="['pay-method', { active: payType === 'ALIPAY' }]" @click="payType = 'ALIPAY'">
            💙 支付宝
          </div>
        </div>
        <button class="pay-btn" :disabled="paying" @click="confirmPay">
          {{ paying ? '支付中…' : `模拟支付 ¥${fmtMoney(selectedPlan.price_fen)}` }}
        </button>
        <p class="cashier-tip">演示环境：点击即模拟支付成功，权益实时到账</p>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
.membership-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 24px 28px; margin-bottom: 20px;
  background: linear-gradient(120deg, rgba(255,142,123,.16), rgba(180,158,232,.14));
}
.mh-left { display: flex; align-items: center; gap: 16px; }
.mh-crown {
  width: 52px; height: 52px; border-radius: 16px; font-size: 26px; color: #fff;
  background: linear-gradient(135deg, #FF8E7B, #F2A0B6);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 16px rgba(255,142,123,.35);
}
.mh-title { margin: 0; font-size: 20px; font-weight: 700; color: #3d3848; }
.mh-sub { margin: 4px 0 0; font-size: 13px; color: #82789a; }
.mh-count { color: #FF8E7B; font-size: 15px; }
.mh-right { text-align: center; }
.mh-num { font-size: 30px; font-weight: 800; color: #FF8E7B; line-height: 1.1; }
.mh-right.member .mh-num { color: #B49EE8; }
.mh-num-label { font-size: 12px; color: #82789a; }

.section-title { font-size: 15px; font-weight: 700; color: #3d3848; margin: 0 0 12px; }

.plans-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px; margin-bottom: 24px;
}
.plan-card {
  position: relative; padding: 22px 18px; border-radius: 18px; cursor: pointer;
  border: 2px solid transparent; transition: all .18s;
}
.plan-card:hover { transform: translateY(-3px); border-color: rgba(255,142,123,.5); }
.plan-member:hover { border-color: rgba(180,158,232,.55); }
.plan-disabled { opacity: .55; cursor: not-allowed; }
.plan-tag {
  position: absolute; top: -10px; left: 16px; padding: 3px 10px; border-radius: 12px;
  font-size: 11px; color: #fff; font-weight: 600;
  background: linear-gradient(90deg, #FF8E7B, #F2A0B6);
}
.plan-name { font-size: 15px; font-weight: 700; color: #3d3848; }
.plan-price { margin-top: 10px; color: #FF8E7B; }
.price-cur { font-size: 14px; font-weight: 700; }
.price-num { font-size: 30px; font-weight: 800; }
.price-suffix { font-size: 12px; color: #82789a; margin-left: 4px; }
.plan-origin {
  font-size: 12px; color: #b6aec4; text-decoration: line-through; margin-top: 2px;
}
.plan-desc { list-style: none; padding: 0; margin: 12px 0 14px; font-size: 12px; color: #82789a; }
.plan-desc li { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
.plan-cta {
  text-align: center; padding: 8px 0; border-radius: 10px; font-size: 13px; font-weight: 600;
  background: rgba(0,0,0,.06); color: #82789a;
}
.plan-cta.ok {
  color: #fff; background: linear-gradient(90deg, #FF8E7B, #F2A0B6);
  box-shadow: 0 4px 12px rgba(255,142,123,.3);
}
.plan-member .plan-cta.ok { background: linear-gradient(90deg, #B49EE8, #D4C8F0); box-shadow: 0 4px 12px rgba(180,158,232,.3); }

.orders { padding: 8px 20px; border-radius: 16px; }
.order-row {
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
  padding: 14px 0; border-bottom: 1px solid rgba(0,0,0,.05);
}
.order-row:last-child { border-bottom: none; }
.order-left { display: flex; flex-direction: column; gap: 2px; }
.order-name { font-size: 14px; font-weight: 600; color: #3d3848; }
.order-no { font-size: 12px; color: #b6aec4; }
.order-right { display: flex; align-items: center; gap: 14px; }
.order-status { font-size: 12px; color: #82789a; }
.order-status.paid { color: #3CCDB6; font-weight: 600; }
.order-amount { font-size: 15px; font-weight: 700; color: #3d3848; }
.order-time { font-size: 12px; color: #b6aec4; }

.cashier { text-align: center; padding: 6px 0 2px; }
.cashier-title { font-size: 16px; font-weight: 700; color: #3d3848; margin: 0 0 16px; }
.cashier-plan { font-size: 13px; color: #82789a; }
.cashier-amount { font-size: 38px; font-weight: 800; color: #3d3848; margin: 6px 0; }
.cashier-benefit { font-size: 12px; color: #3CCDB6; margin-bottom: 18px; }
.pay-methods { display: flex; gap: 10px; margin-bottom: 18px; }
.pay-method {
  flex: 1; padding: 10px 0; border-radius: 10px; font-size: 13px; cursor: pointer;
  border: 1.5px solid rgba(0,0,0,.08); color: #82789a; transition: all .15s;
}
.pay-method.active { border-color: #FF8E7B; color: #FF8E7B; font-weight: 600; background: rgba(255,142,123,.08); }
.pay-btn {
  width: 100%; padding: 12px 0; border: none; border-radius: 12px; cursor: pointer;
  font-size: 15px; font-weight: 700; color: #fff;
  background: linear-gradient(90deg, #FF8E7B, #F2A0B6);
  box-shadow: 0 6px 16px rgba(255,142,123,.35);
}
.pay-btn:disabled { opacity: .6; cursor: wait; }
.cashier-tip { font-size: 11px; color: #b6aec4; margin: 12px 0 0; }
</style>
