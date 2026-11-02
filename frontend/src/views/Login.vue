<script setup lang="ts">
import { ref, reactive, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { sendSmsCode } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const form = reactive({ phone: '', code: '' })
const loading = ref(false)
const demoLoading = ref(false)
const counting = ref(false)
const countdown = ref(60)
let timer: any = null

async function handleSendSms() {
  if (!/^1\d{10}$/.test(form.phone)) {
    message.warning('请输入正确的 11 位手机号')
    return
  }
  try {
    const res: any = await sendSmsCode(form.phone, 'LOGIN')
    // 演示账号不发真实短信，直接提示走一键登录
    if (res?.demo) {
      message.info('演示账号无需验证码，请直接点「演示账号直接体验」')
      return
    }
    if (res?.code) {
      // 调试模式(未配置真实短信)：不再自动填入，验证码以后端控制台为准
      console.log('[调试模式] 验证码:', res.code)
      message.warning('验证码已发送（调试模式：请查看后端控制台）')
    } else {
      message.success('验证码已发送，请注意查收短信')
    }
    counting.value = true
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) {
        clearInterval(timer)
        counting.value = false
      }
    }, 1000)
  } catch {
    /* error handled in request interceptor */
  }
}

async function handleLogin() {
  if (!/^1\d{10}$/.test(form.phone)) {
    message.warning('请输入正确的手机号')
    return
  }
  if (!form.code || form.code.length < 4) {
    message.warning('请输入验证码')
    return
  }
  loading.value = true
  try {
    await userStore.login(form.phone, form.code)
    message.success('登录成功')
    router.push('/home')
  } finally {
    loading.value = false
  }
}

// 演示账号：不需要手机号和验证码，直接进入；每次进入会清空上次演示数据
async function handleDemoLogin() {
  demoLoading.value = true
  try {
    await userStore.loginDemo()
    message.success('已进入演示账号')
    router.push('/home')
  } finally {
    demoLoading.value = false
  }
}

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="login-shell">
    <!-- 左：品牌与五维评估 -->
    <section class="hero">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <rect x="9" y="2.5" width="6" height="11" rx="3" />
            <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
            <path d="M12 17.5V21" />
            <path d="M8.5 21h7" />
          </svg>
        </div>
        <div>
          <div class="brand-name">模拟面试 AI 助手</div>
          <div class="brand-tag">AI 面试官，陪你练到上岸</div>
        </div>
      </div>

      <div class="hero-rule"></div>
      <h1>把每一次回答，<br />练成底气。</h1>
      <p class="hero-sub">AI 面试官，实时追问，五维评估</p>
      <p class="hero-note">从简历到报告，完整走一遍真实面试。</p>

      <div class="hero-wave" aria-hidden="true">
        <span
          v-for="i in 36"
          :key="i"
          :style="{
            height: `${14 + ((i * 29) % 46)}px`,
            animationDelay: `${(i % 8) * 0.12}s`
          }"
        ></span>
      </div>
      <p class="hero-caption">每一次练习，都算数。</p>
    </section>

    <!-- 右：登录卡片 -->
    <section class="login-card glass-card">
      <div class="card-head">
        <h2>登录</h2>
        <p>继续你的面试练习</p>
      </div>

      <form @submit.prevent="handleLogin">
        <label class="field">
          <span>手机号</span>
          <input
            v-model="form.phone"
            type="tel"
            inputmode="numeric"
            autocomplete="tel"
            maxlength="11"
            placeholder="请输入 11 位手机号"
          />
        </label>

        <label class="field">
          <span>验证码</span>
          <div class="code-row">
            <input
              v-model="form.code"
              type="text"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength="6"
              placeholder="请输入验证码"
            />
            <button
              type="button"
              class="send-btn"
              :disabled="counting"
              @click="handleSendSms"
            >
              {{ counting ? `${countdown} 秒` : '发送验证码' }}
            </button>
          </div>
        </label>

        <button type="submit" class="primary-btn" :disabled="loading">
          {{ loading ? '正在进入…' : '进入面试' }}
        </button>
      </form>

      <div class="or"><span>或</span></div>

      <button type="button" class="demo-btn" :disabled="demoLoading" @click="handleDemoLogin">
        <span class="demo-title">{{ demoLoading ? '正在进入…' : '演示账号直接体验' }}</span>
        <span class="demo-meta">18888888888，无需验证码</span>
      </button>
      <p class="demo-note">次数无限，每次进入自动清空上次演示数据</p>

      <p class="agreement">
        登录即同意 <a href="javascript:void(0)">《用户协议》</a> 和
        <a href="javascript:void(0)">《隐私政策》</a>
      </p>
    </section>
  </div>
</template>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
  align-items: center;
  gap: clamp(32px, 5vw, 84px);
  padding: 48px clamp(24px, 6vw, 96px);
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei',
    'Segoe UI', sans-serif;
  color: #3d3848;
}

/* ============ 左：品牌 + 评估卡 ============ */
.hero {
  width: 100%;
  max-width: 580px;
  justify-self: end;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  border-radius: 14px;
  background: linear-gradient(135deg, #ff8e7b 0%, #ffb4a0 50%, #f2a0b6 100%);
  color: #fff;
  box-shadow: 0 8px 20px rgba(255, 142, 123, 0.35);
}

.brand-mark svg {
  width: 23px;
  height: 23px;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: #3d3848;
}

.brand-tag {
  margin-top: 3px;
  font-size: 12px;
  color: #82789a;
}

.hero-rule {
  width: 56px;
  height: 4px;
  margin: 34px 0 24px;
  border-radius: 4px;
  background: linear-gradient(90deg, #ff8e7b 0%, #3ccdb6 100%);
}

.hero h1 {
  margin: 0;
  font-size: clamp(36px, 4vw, 56px);
  line-height: 1.14;
  font-weight: 800;
  letter-spacing: -0.035em;
  color: #3d3848;
}

.hero-sub {
  margin: 16px 0 0;
  font-size: 14px;
  color: #82789a;
}

.hero-note {
  margin: 26px 0 0;
  font-size: 13px;
  line-height: 1.8;
  color: #82789a;
}

.hero-wave {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 46px;
  margin-top: 32px;
}

.hero-wave span {
  width: 3px;
  border-radius: 3px;
  background: linear-gradient(180deg, #ff8e7b 0%, #b49ee8 55%, #3ccdb6 100%);
  opacity: 0.72;
  transform-origin: center;
  animation: waveMove 1.8s ease-in-out infinite;
}

.hero-caption {
  margin: 12px 0 0;
  font-size: 12px;
  letter-spacing: 0.04em;
  color: #a49bb3;
}

@keyframes waveMove {
  0%, 100% { transform: scaleY(0.5); opacity: 0.55; }
  50% { transform: scaleY(1); opacity: 0.9; }
}

@media (prefers-reduced-motion: reduce) {
  .hero-wave span {
    animation: none;
  }
}

/* ============ 右：登录卡片 ============ */
.login-card {
  width: 100%;
  max-width: 420px;
  justify-self: start;
  padding: 38px 36px 30px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.78);
  box-shadow: 0 12px 40px rgba(140, 110, 170, 0.12), 0 24px 60px rgba(140, 110, 170, 0.08);
}

.card-head h2 {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.025em;
  color: #3d3848;
}

.card-head p {
  margin: 8px 0 26px;
  font-size: 13px;
  color: #82789a;
}

.field {
  display: block;
  margin-bottom: 16px;
}

.field > span {
  display: block;
  margin-bottom: 7px;
  font-size: 12px;
  color: #82789a;
}

.field input {
  width: 100%;
  padding: 11px 14px;
  font: inherit;
  font-size: 14px;
  color: #3d3848;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e8e3dc;
  border-radius: 10px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field input::placeholder {
  color: #b3aac6;
}

.field input:focus {
  border-color: rgba(255, 142, 123, 0.7);
  box-shadow: 0 0 0 3px rgba(255, 142, 123, 0.12);
}

.code-row {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.code-row input {
  flex: 1;
  min-width: 0;
}

.send-btn {
  flex: 0 0 auto;
  padding: 0 12px;
  font-size: 12px;
  color: #ff8e7b;
  background: rgba(255, 142, 123, 0.09);
  border: 1px solid rgba(255, 142, 123, 0.35);
  border-radius: 10px;
  white-space: nowrap;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  background: rgba(255, 142, 123, 0.16);
  border-color: rgba(255, 142, 123, 0.55);
}

.send-btn:disabled {
  color: #b3aac6;
  background: #f5f2ed;
  border-color: #e8e3dc;
  cursor: not-allowed;
}

.primary-btn {
  width: 100%;
  margin-top: 8px;
  padding: 13px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #ff8e7b 0%, #ffb4a0 50%, #f2a0b6 100%);
  border: 0;
  border-radius: 10px;
  box-shadow: 0 6px 18px rgba(255, 142, 123, 0.35);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(255, 142, 123, 0.45);
}

.primary-btn:active:not(:disabled) {
  transform: translateY(0);
}

.primary-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}

.or {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 20px 0 16px;
  font-size: 11px;
  color: #b3aac6;
}

.or::before,
.or::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e8e3dc;
}

.demo-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 11px 14px;
  text-align: left;
  background: rgba(60, 205, 182, 0.08);
  border: 1px solid rgba(60, 205, 182, 0.28);
  border-radius: 10px;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.demo-btn:hover:not(:disabled) {
  background: rgba(60, 205, 182, 0.14);
  border-color: rgba(60, 205, 182, 0.45);
}

.demo-btn:disabled {
  opacity: 0.7;
  cursor: wait;
}

.demo-title {
  font-size: 13px;
  font-weight: 600;
  color: #2f9e8a;
}

.demo-meta {
  font-size: 10.5px;
  color: #82789a;
  white-space: nowrap;
}

.demo-note {
  margin: 8px 0 0;
  font-size: 11px;
  color: #a49bb3;
}

.agreement {
  margin: 24px 0 0;
  font-size: 11px;
  line-height: 1.7;
  color: #a49bb3;
}

.agreement a {
  color: #82789a;
  border-bottom: 1px solid #e8e3dc;
}

/* ============ 响应式 ============ */
@media (max-width: 920px) {
  .login-shell {
    grid-template-columns: 1fr;
    gap: 30px;
    padding: 36px 24px 44px;
  }

  .hero {
    max-width: 640px;
    justify-self: center;
    text-align: center;
  }

  .brand {
    justify-content: center;
  }

  .hero-rule {
    margin: 28px auto 20px;
  }

  .hero h1 {
    font-size: clamp(30px, 7.2vw, 42px);
  }

  .hero-wave {
    justify-content: center;
  }

  .hero-caption {
    text-align: center;
  }

  .login-card {
    max-width: 420px;
    justify-self: center;
  }
}

@media (max-width: 640px) {
  .login-card {
    padding: 30px 22px 24px;
  }
}

@media (max-width: 420px) {
  .demo-btn {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
}
</style>
