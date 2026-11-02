<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, computed, onUnmounted } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { startSession, askNext, askNextStream, submitAnswer, endSession, getSessionDetail, heartbeat } from '@/api/interview'
import ChatBubble from '@/components/ChatBubble.vue'
import Waveform from '@/components/Waveform.vue'

const route = useRoute()
const router = useRouter()
const sessionId = computed(() => Number(route.params.id))

const statusText = ref('面试官：AI 面试官')
// 本场练习模式名（完整模拟面试 / 专项打磨训练 / 面试前冲刺模式）
const modeName = ref('')
const interviewerAvatar = ref('/images/interviewer_digital.svg?v=1')
const questionIdx = ref(0)
// 本场建议时长（分钟，由练习模式决定）—— 面试官按这个节奏自己决定何时收尾
const timeLimitMin = ref(0)
// 面试官已经收尾、本场结束（输入区换成"查看报告"）
const interviewOver = ref(false)
// 结束面板上显示的原因（正常结束 / 离开太久自动结束）
const overReason = ref('🎬 本场面试到此结束，面试官已经做了收尾。')
// 面试官正在问"还有没有想问的"（提醒用户：回"没有"就结束）
const closingAsked = ref(false)
const elapsed = ref(0)
const messages = reactive<Array<{ role: 'ai' | 'user'; text: string; time?: string; question_id?: number }>>([])

// 人设 → 头像映射（AI 虚拟形象）
const PERSONA_AVATAR_MAP: Record<string, string> = {
  '温和鼓励型': '/images/interviewer_digital.svg?v=1',
  '压力追问型': '/images/interviewer_digital.svg?v=1',
  '按公司定制': '/images/interviewer_digital.svg?v=1',
}

const textInput = ref('')
const sending = ref(false)
const ended = ref(false)
// 本场会话的详情（loadSession 拉一次，恢复对话时复用，不用再请求一遍）
const sessionDetail = ref<any>(null)
// 已经确认过要离开（结束面试跳报告页时用，免得再弹一次"确定离开吗"）
const leavingConfirmed = ref(false)

// === 语音识别 ===
const isListening = ref(false)       // 正在听用户说话
const voiceEnabled = ref(true)        // AI 语音播报开关
const interimText = ref('')           // 实时识别中的文字
let recognition: any = null

// 检查浏览器是否支持语音识别
const speechSupported = typeof window !== 'undefined' && (
  !!(window as any).SpeechRecognition || !!(window as any).webkitSpeechRecognition
)

// 检查浏览器是否支持语音合成
const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window

function initSpeechRecognition() {
  if (!speechSupported) return
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  recognition = new SR()
  recognition.lang = 'zh-CN'
  recognition.continuous = true          // 持续识别
  recognition.interimResults = true      // 返回中间结果

  recognition.onresult = (event: any) => {
    let finalText = ''
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript
      if (event.results[i].isFinal) {
        finalText += transcript
      } else {
        interim += transcript
      }
    }
    if (finalText) {
      // 把最终结果追加到输入框
      textInput.value = (textInput.value + finalText).trim()
    }
    interimText.value = interim
  }

  recognition.onerror = (event: any) => {
    if (event.error === 'no-speech') return // 没检测到语音，忽略
    if (event.error === 'aborted') return   // 手动中止，忽略
    console.warn('语音识别错误:', event.error)
  }

  recognition.onend = () => {
    // 如果还在听模式，重启识别（避免短暂停顿后中断）
    if (isListening.value) {
      try { recognition.start() } catch {}
    }
  }
}

function startListening() {
  if (!speechSupported) {
    message.warning('当前浏览器不支持语音识别，请使用 Chrome 或 Edge 浏览器')
    return
  }
  if (!recognition) initSpeechRecognition()
  isListening.value = true
  interimText.value = ''
  try {
    recognition.start()
  } catch {
    // 可能已在运行，忽略
  }
}

function stopListening() {
  isListening.value = false
  if (recognition) {
    try { recognition.stop() } catch {}
  }
  interimText.value = ''
}

function toggleListen() {
  if (isListening.value) {
    stopListening()
  } else {
    startListening()
  }
}

// === AI 语音播报 ===
function speak(text: string) {
  if (!voiceEnabled.value || !ttsSupported) return
  // 取消之前的播报
  window.speechSynthesis.cancel()
  // 清理文字（去掉 emoji 和评分符号）
  const cleanText = text.replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}📊✨⚠️💡]/gu, '').trim()
  if (!cleanText) return
  const utter = new SpeechSynthesisUtterance(cleanText)
  utter.lang = 'zh-CN'
  utter.rate = 1.0
  utter.pitch = 1.0
  // 尝试使用中文女声
  const voices = window.speechSynthesis.getVoices()
  const zhVoice = voices.find((v: any) => v.lang.startsWith('zh'))
  if (zhVoice) utter.voice = zhVoice
  window.speechSynthesis.speak(utter)
}

function toggleVoice() {
  voiceEnabled.value = !voiceEnabled.value
  if (!voiceEnabled.value && ttsSupported) {
    window.speechSynthesis.cancel()
  }
  message.info(voiceEnabled.value ? 'AI 语音播报已开启' : 'AI 语音播报已关闭')
}

let timer: any = null
// 心跳定时器：每 60 秒告诉后端"我还在面试页面上"。
// 心跳一停（关页面/关浏览器/电脑休眠），后端 10 分钟后就会把这场面试自动结束。
let beatTimer: any = null
const HEARTBEAT_MS = 60000

function startHeartbeat() {
  const beat = async () => {
    // 本场已经结束了，不用再发了
    if (interviewOver.value) {
      clearInterval(beatTimer)
      return
    }
    try {
      const res: any = await heartbeat(sessionId.value)
      // 后端说这场已经不在进行中了（离开太久被自动结束了）→ 立刻切到结束面板
      if (res && res.is_running === false && !interviewOver.value) {
        interviewOver.value = true
        overReason.value = '⏸️ 这场面试因为离开超过 10 分钟，已经自动结束了。'
        clearInterval(timer)
        clearInterval(beatTimer)
      }
    } catch {
      /* 网络抖一下而已，下一轮再试 */
    }
  }
  beat()
  beatTimer = setInterval(beat, HEARTBEAT_MS)
}

function fmtTime(s: number) {
  const m = String(Math.floor(s / 60)).padStart(2, '0')
  const sec = String(s % 60).padStart(2, '0')
  return `${m}:${sec}`
}

const scrollerRef = ref<HTMLElement | null>(null)
async function scrollBottom() {
  await nextTick()
  if (scrollerRef.value) {
    scrollerRef.value.scrollTop = scrollerRef.value.scrollHeight
  }
}

async function loadSession() {
  try {
    const detail: any = await getSessionDetail(sessionId.value)
    sessionDetail.value = detail
    if (detail?.persona_name) {
      statusText.value = `面试官：${detail.persona_name}`
      interviewerAvatar.value = PERSONA_AVATAR_MAP[detail.persona_name] || PERSONA_AVATAR_MAP['压力追问型']
    }
    if (detail?.mode_name) modeName.value = detail.mode_name
    // 本场建议时长（由练习模式决定，约 30 分钟）
    if (detail?.time_limit_min) timeLimitMin.value = detail.time_limit_min
    // 刷新页面后恢复状态：2=FINISHED（正常结束），4=EXPIRED（离开太久自动结束）
    if (detail?.status === 2) {
      interviewOver.value = true
    } else if (detail?.status === 4) {
      interviewOver.value = true
      overReason.value = '⏸️ 这场面试因为离开超过 10 分钟，已经自动结束了。'
    }
  } catch { /* ignore */ }
}

/**
 * 回到一场已经开始的面试时，把之前的问答还原出来，接着往下聊 ——
 * 不要当成新的一场重新出题（那样"继续之前的面试"就名不副实了）。
 */
async function restoreTranscript(): Promise<boolean> {
  const qs: any[] = Array.isArray(sessionDetail.value?.questions)
    ? sessionDetail.value.questions
    : []
  if (!qs.length) return false

  for (const q of qs) {
    messages.push({ role: 'ai', text: q.question_text, question_id: q.id })
    const answered = q.answer?.answer_text
    if (answered) messages.push({ role: 'user', text: answered })
    if (q.intent === '收尾环节') closingAsked.value = true
  }
  questionIdx.value = qs.length

  // 计时接着上一场走，不是从 0 开始
  const startedAt = sessionDetail.value?.start_at
  if (startedAt) {
    const secs = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000)
    if (secs > 0) elapsed.value = secs
  }
  await scrollBottom()
  return true
}

async function initInterview() {
  try {
    await startSession(sessionId.value)
  } catch { /* 已经启动过了，忽略 */ }

  const restored = await restoreTranscript()
  // 新的一场才出题；已经是接着聊的，等用户回答后自然推进
  if (!restored && !interviewOver.value) {
    await nextQuestion()
  }
  timer = setInterval(() => { elapsed.value++ }, 1000)
}

async function nextQuestion(parentId?: number) {
  // 面试官已经收尾了，不再出新题（人设/时长决定，不由用户点按钮）
  if (interviewOver.value) return
  closingAsked.value = false
  if (!parentId) {
    questionIdx.value++
  }

  // 先插入一个空的 AI 气泡,边收边填(打字机效果)
  const idx = messages.length
  messages.push({ role: 'ai', text: '', question_id: undefined })
  await scrollBottom()

  try {
    await askNextStream(
      sessionId.value,
      (delta) => {
        messages[idx].text += delta
        scrollBottom()
      },
      (meta) => {
        messages[idx].question_id = meta.question_id
        // 面试官在问"还有没有想问的"：回"没有"就结束，否则继续聊
        if (meta.intent === '收尾环节') closingAsked.value = true
      },
    )
    // AI 语音播报问题
    speak(messages[idx].text)
  } catch (e: any) {
    // 流式失败 → 退回一次性接口,保证功能不丢
    messages.splice(idx, 1)
    try {
      const q: any = await askNext(sessionId.value, parentId)
      const text = q?.question_text || q?.text
      if (!text) {
        ended.value = true
        clearInterval(timer)
        messages.push({ role: 'ai', text: '模拟面试已结束，感谢你的参与！' })
        speak('模拟面试已结束，感谢你的参与！')
        return
      }
      messages.push({ role: 'ai', text, question_id: q.question_id || q.id })
      if (q?.intent === '收尾环节') closingAsked.value = true
      await scrollBottom()
      speak(text)
    } catch {
      message.warning('获取问题失败')
    }
  }
}

async function sendAnswer() {
  const answer = textInput.value.trim()
  if (!answer || sending.value) return
  // 如果正在听语音，先停止
  if (isListening.value) stopListening()
  textInput.value = ''
  sending.value = true
  const lastAi = [...messages].reverse().find(m => m.role === 'ai')
  const questionId = lastAi?.question_id
  const startElapsed = elapsed.value
  messages.push({ role: 'user', text: answer })
  await scrollBottom()
  try {
    const res: any = await submitAnswer(sessionId.value, {
      question_id: Number(questionId),
      answer_text: answer,
      duration_sec: elapsed.value - startElapsed
    })
    // 面试官问"还有想问的吗"，你回"没有了" → 本场就此结束，不再出题
    if (res?.interview_finished) {
      interviewOver.value = true
      clearInterval(timer)
      if (ttsSupported) window.speechSynthesis.cancel()
      return
    }
    // 显示 AI 对回答的即时评价
    if (res?.score != null || res?.improvement || res?.strengths) {
      let feedback = ''
      if (res.score != null) feedback += `📊 评分：${Number(res.score).toFixed(1)}\n`
      if (res.strengths) feedback += `✨ 亮点：${res.strengths}\n`
      if (res.weaknesses) feedback += `⚠️ 不足：${res.weaknesses}\n`
      if (res.improvement) feedback += `💡 建议：${res.improvement}`
      if (feedback) {
        messages.push({ role: 'ai', text: feedback.trim() })
        await scrollBottom()
        // 播报反馈（简短版）
        speak(`评分${Number(res.score).toFixed(0)}分。${res.strengths || ''}。${res.improvement || ''}`)
      }
    }
    // 等播报完再问下一题
    setTimeout(() => {
      if (res?.should_followup && questionId) {
        nextQuestion(questionId)
      } else {
        nextQuestion()
      }
    }, 500)
  } catch {
    sending.value = false
  }
  sending.value = false
}

// 结束会话并跳到评估报告
async function goReport() {
  if (isListening.value) stopListening()
  if (ttsSupported) window.speechSynthesis.cancel()
  try {
    await endSession(sessionId.value)
  } catch {}
  clearInterval(timer)
  // 这是主动结束，不是误点 —— 放行，别再弹"确定要离开吗"
  leavingConfirmed.value = true
  router.push(`/report/${sessionId.value}`)
}

function handleEnd() {
  // 面试官已经收尾了，不用再确认一次，直接看报告
  if (interviewOver.value) {
    goReport()
    return
  }
  if (isListening.value) stopListening()
  if (ttsSupported) window.speechSynthesis.cancel()
  Modal.confirm({
    title: '确定结束本次面试？',
    content: '结束后将进入评估报告',
    okText: '结束并查看报告',
    cancelText: '继续面试',
    // Ant Design Vue 的按钮属性类型里没有 class，运行时支持，这里显式放开
    okButtonProps: { class: 'btn-coral' } as any,
    onOk: goReport
  })
}

/**
 * 面试进行中误点导航栏时拦一下 —— 直接跳走的话，这场面试的对话就找不回来了。
 * 选「继续面试」就留在原页面；确实要走也不拦着，进度会保留，之后能回去继续。
 */
onBeforeRouteLeave(async () => {
  // 已经结束 / 本来就没开始 / 自己确认要走的，都不拦
  if (leavingConfirmed.value || interviewOver.value || ended.value || !messages.length) {
    return true
  }
  return await new Promise<boolean>((resolve) => {
    Modal.confirm({
      title: '面试还没结束，确定要离开吗？',
      content: '这场面试的进度会保留，之后可以从「开始面试」页面点「继续这场面试」回来。',
      okText: '离开',
      cancelText: '继续面试',
      okButtonProps: { danger: true },
      onOk: () => {
        leavingConfirmed.value = true
        resolve(true)
      },
      onCancel: () => resolve(false)
    })
  })
})

onMounted(async () => {
  // 预加载语音列表（某些浏览器需要异步获取）
  if (ttsSupported) {
    window.speechSynthesis.getVoices()
  }
  await loadSession()
  await initInterview()
  // 面试已经结束了就不用再发心跳
  if (!interviewOver.value) startHeartbeat()
})

onUnmounted(() => {
  if (isListening.value) stopListening()
  if (ttsSupported) window.speechSynthesis.cancel()
  if (timer) clearInterval(timer)
  // 离开页面 = 停心跳，后端 10 分钟后会把这场面试自动结束
  if (beatTimer) clearInterval(beatTimer)
})
</script>

<template>
  <div class="interview-page">
    <!-- 顶部状态条 -->
    <div class="status-bar glass-card">
      <!-- 面试官形象 -->
      <div class="interviewer-card">
        <img :src="interviewerAvatar" alt="面试官" class="interviewer-img" />
        <div class="interviewer-info">
          <div class="interviewer-name">{{ statusText.replace('面试官：', '') }}</div>
          <div class="interviewer-tag">AI 面试官</div>
        </div>
      </div>
      <div class="status-divider"></div>
      <div class="status-item" v-if="modeName">
        <span class="label">🎯 {{ modeName }}</span>
      </div>
      <div class="status-item">
        <span class="label">第 {{ questionIdx }} 题</span>
      </div>
      <div class="status-item">
        <span class="label">
          ⏱️ {{ fmtTime(elapsed) }}<span v-if="timeLimitMin" class="limit-tip"> / 约 {{ timeLimitMin }} 分钟</span>
        </span>
      </div>
      <!-- AI 语音播报开关 -->
      <button class="voice-toggle" :class="{ active: voiceEnabled }" @click="toggleVoice" title="AI 语音播报">
        <span v-if="voiceEnabled">🔊</span>
        <span v-else>🔇</span>
      </button>
      <a-button class="btn-outline" size="small" @click="handleEnd">
        {{ interviewOver ? '查看报告' : '结束面试' }}
      </a-button>
    </div>

    <!-- 对话流 -->
    <div class="chat-wrap">
      <div class="chat-scroller" ref="scrollerRef">
        <div class="chat-inner">
          <template v-for="(m, idx) in messages" :key="idx">
            <ChatBubble :role="m.role" :text="m.text" :interviewer-avatar="interviewerAvatar" />
          </template>
        </div>
      </div>
    </div>

    <!-- 底部输入区 -->
    <div class="input-wrap">
      <!-- 面试官已经收尾：本场结束，输入区换成查看报告的入口 -->
      <div v-if="interviewOver" class="over-panel">
        <div class="over-text">{{ overReason }}</div>
        <a-button class="btn-coral" size="large" @click="handleEnd">查看评估报告</a-button>
      </div>
      <template v-else>
        <!-- 面试官在问是否还有想问的：告诉用户回"没有"就会结束 -->
        <div v-if="closingAsked" class="wrap-hint">
          🎬 面试官在问你还有没有想了解的 —— 有问题就直接问，回「没有」这场面试就结束。
        </div>
        <!-- 实时语音识别状态 -->
        <div v-if="isListening" class="wave-area">
          <Waveform />
          <div class="wave-tip">
            <span class="listening-dot"></span>
            正在聆听{{ interimText ? '：' + interimText : '…' }}
          </div>
        </div>

        <div class="input-row">
          <!-- 语音输入按钮 -->
          <button
            :class="['voice-btn', { active: isListening }]"
            @click="toggleListen"
            :title="isListening ? '点击停止语音输入' : '点击开始语音输入'"
          >
            <span v-if="isListening" class="pulse-ring"></span>
            <span class="mic-icon">{{ isListening ? '🔴' : '🎤' }}</span>
          </button>

          <!-- 文本输入 -->
          <a-input
            v-model:value="textInput"
            size="large"
            :placeholder="isListening ? '语音识别中…说话即可输入' : '点击麦克风语音输入，或直接打字…'"
            :disabled="sending"
            @press-enter="sendAnswer"
          >
            <template #suffix>
              <a-button class="btn-coral send" size="small" :loading="sending" @click="sendAnswer">发送</a-button>
            </template>
          </a-input>
        </div>

        <!-- 提示 -->
        <div class="bottom-tip">
          <span v-if="!speechSupported">⚠️ 当前浏览器不支持语音识别，建议使用 Chrome 或 Edge</span>
          <span v-else>💡 点击 🎤 开始说话，语音会自动转为文字，说完点发送</span>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.interview-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 72px);
  max-width: 900px;
  margin: 0 auto;
  padding: 16px;
  gap: 12px;
}

.status-bar {
  padding: 12px 18px;
  display: flex;
  gap: 16px;
  align-items: center;
}
.interviewer-card {
  display: flex;
  align-items: center;
  gap: 10px;
}
.interviewer-img {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #B49EE8;
  box-shadow: 0 2px 8px rgba(180,158,232,0.3);
}
.interviewer-name {
  font-size: 14px;
  font-weight: 600;
  color: #3d3848;
}
.interviewer-tag {
  font-size: 11px;
  color: #B49EE8;
}
.status-divider {
  width: 1px;
  height: 36px;
  background: rgba(140,110,170,0.15);
  margin: 0 4px;
}
.status-bar .label {
  font-size: 13px;
  color: #3d3848;
  font-weight: 500;
}
.status-item.flex1 { flex: 1; }

.voice-toggle {
  border: none;
  background: rgba(140,110,170,0.1);
  border-radius: 50%;
  width: 36px;
  height: 36px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.15s;
}
.voice-toggle:hover { background: rgba(140,110,170,0.2); }
.voice-toggle.active { background: rgba(60,205,182,0.2); }

.chat-wrap {
  flex: 1;
  min-height: 0;
  border-radius: 14px;
  background: rgba(255,255,255,0.75);
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 16px rgba(140,110,170,0.06);
  border: 1px solid rgba(232,227,220,0.6);
}
.chat-scroller {
  height: 100%;
  overflow-y: auto;
  padding: 24px 28px;
}
.chat-inner {
  display: flex;
  flex-direction: column;
}

.input-wrap {
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(12px);
  border-radius: 14px;
  border: 1px solid rgba(232,227,220,0.6);
  padding: 16px;
  box-shadow: 0 4px 16px rgba(140,110,170,0.06);
}

/* 面试官问"还有想问的吗"时的提醒条 —— 薄荷绿细条，不抢输入框注意力 */
.wrap-hint {
  margin-bottom: 12px;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  color: #28695c;
  background: rgba(60, 205, 182, 0.1);
  border: 1px solid rgba(60, 205, 182, 0.28);
}

/* 面试结束后的收尾面板 —— 取代输入框，把用户引向评估报告 */
.over-panel {
  text-align: center;
  padding: 10px 0 4px;
}
.over-text {
  font-size: 15px;
  color: #3d3848;
  margin-bottom: 14px;
}
/* 时间后面的"约 30 分钟"小字 */
.limit-tip {
  color: #8b83a0;
  font-weight: 400;
}

.wave-area {
  text-align: center;
  padding: 6px 0;
}
.wave-tip {
  font-size: 13px;
  color: #FF8E7B;
  margin-top: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.listening-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #FF8E7B;
  animation: blink 1s infinite;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.input-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.voice-btn {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #FF8E7B 0%, #FFB4A0 50%, #F2A0B6 100%);
  color: #fff;
  font-size: 24px;
  box-shadow: 0 6px 20px rgba(255,142,123,0.4);
  transition: transform 0.15s;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.voice-btn:hover { transform: scale(1.05); }
.voice-btn.active {
  box-shadow: 0 0 0 6px rgba(255,142,123,0.25), 0 0 24px rgba(255,142,123,0.5);
  animation: pulse 1.4s infinite;
}
.pulse-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid rgba(255,142,123,0.5);
  animation: ring 1.5s infinite;
}
@keyframes ring {
  0% { transform: scale(1); opacity: 1; }
  100% { transform: scale(1.5); opacity: 0; }
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 6px rgba(255,142,123,0.25), 0 6px 20px rgba(255,142,123,0.4); }
  50% { box-shadow: 0 0 0 16px rgba(255,142,123,0.08), 0 6px 20px rgba(255,142,123,0.4); }
  100% { box-shadow: 0 0 0 6px rgba(255,142,123,0.25), 0 6px 20px rgba(255,142,123,0.4); }
}
.mic-icon { filter: drop-shadow(0 2px 6px rgba(0,0,0,0.15)); z-index: 1; }

.text-area .send { border-radius: 8px; }

.bottom-tip {
  text-align: center;
  font-size: 12px;
  color: #82789a;
  margin-top: 8px;
}
</style>
