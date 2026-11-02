<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { createSession, listSessions } from '@/api/interview'
import { getPracticeModes, getPersonas, getTechDirections } from '@/api/dictionary'
import { listTargetPositions, getUserTechDirections, listResumes, saveUserTechDirections, getResume } from '@/api/resume'
import { message, Modal } from 'ant-design-vue'

const router = useRouter()

const practiceModes = ref<any[]>([])
const personas = ref<any[]>([])
const techDirections = ref<any[]>([])
const targetPositions = ref<any[]>([])
const resumes = ref<any[]>([])
const selectedResume = ref<number | null>(null)
const selectedMode = ref<number | null>(null)
const selectedPersona = ref<number | null>(null)
const selectedTechIds = ref<number[]>([])
const customTechInput = ref('')
const customTechs = ref<string[]>([])
const selectedDifficulty = ref<number>(3)
const selectedTargetPosition = ref<number | null>(null)
const customPosition = ref('')
const submitting = ref(false)
// 加载中标志：避免加载期间就把"暂无数据"显示出来
const loading = ref(true)

// 档案里只存了一个简历/岗位时，直接用它、折成一行显示；点「更换」才展开选择器
const showPositionPicker = ref(false)
const showResumePicker = ref(false)

// 「按公司定制」人设：有目标岗位就自动读公司名+JD 模仿；没有才让用户自己写风格
const customPersona = ref('')
const selectedPersonaObj = computed(() =>
  personas.value.find((p: any) => p.id === selectedPersona.value)
)
const isCustomPersona = computed(() => selectedPersonaObj.value?.code === 'CUSTOM')
const hasPosition = computed(() => !!selectedTargetPosition.value || !!customPosition.value.trim())

// 有一场没结束的面试时，给个"继续"入口
const unfinished = ref<any>(null)
const unfinishedLabel = computed(() => {
  const u = unfinished.value
  if (!u) return ''
  const mode = practiceModes.value.find((m: any) => m.id === u.practice_mode_id)
  const mins = u.start_at
    ? Math.max(1, Math.round((Date.now() - new Date(u.start_at).getTime()) / 60000))
    : 0
  return `${mode?.name || '模拟面试'} · 已进行 ${mins} 分钟`
})

// 「专项打磨训练」：让用户指定这次要练哪一段材料
const focusTarget = ref('')          // 选中的材料（也是提交给后端的值）
const focusOptions = ref<string[]>([])  // 从所选简历里拉出来的可练材料
const customFocusInput = ref('')     // 自由输入
const focusedModeId = computed(() => practiceModes.value.find((m: any) => m.code === 'FOCUSED')?.id)
const isFocusedMode = computed(() => !!focusedModeId.value && selectedMode.value === focusedModeId.value)

// 换简历就重新拉一遍这份简历里的项目/实习，作为可练材料
watch(selectedResume, async (id) => {
  focusOptions.value = []
  focusTarget.value = ''
  if (!id) return
  try {
    const detail: any = await getResume(Number(id))
    // parsed_struct 后端存的是 JSON 字符串，要解析一次
    let struct: any = detail?.parsed_struct
    if (typeof struct === 'string') {
      try { struct = JSON.parse(struct) } catch { struct = null }
    }
    const opts: string[] = ['自我介绍']
    for (const p of struct?.projects || []) {
      if (p?.project_name) opts.push(`项目：${p.project_name}`)
    }
    for (const it of struct?.internships || []) {
      if (it?.company) opts.push(`实习：${it.company}${it.role ? ' · ' + it.role : ''}`)
    }
    focusOptions.value = opts
  } catch {
    focusOptions.value = ['自我介绍']
  }
})

function positionLabel(tp: any) {
  return tp.company_name ? `${tp.company_name} · ${tp.position_name}` : tp.position_name
}

function resumeLabel(r: any) {
  return `${r.file_name}${r.is_default === 1 ? '（默认）' : ''}`
}

const DIFFICULTY_LABELS: Record<number, string> = {
  1: '入门', 2: '简单', 3: '中等', 4: '较难', 5: '挑战'
}

function toggleTech(id: number) {
  const i = selectedTechIds.value.indexOf(id)
  if (i >= 0) {
    selectedTechIds.value.splice(i, 1)
  } else {
    selectedTechIds.value.push(id)
  }
}

function addCustomTech() {
  const v = customTechInput.value.trim()
  if (!v) return
  if (customTechs.value.includes(v)) {
    message.warning('该方向已添加')
    return
  }
  customTechs.value.push(v)
  customTechInput.value = ''
}

function removeCustomTech(v: string) {
  customTechs.value = customTechs.value.filter((x) => x !== v)
}

// 专项训练：自由输入一段要练的材料
function useCustomFocus() {
  const v = customFocusInput.value.trim()
  if (!v) return
  focusTarget.value = v
  customFocusInput.value = ''
}

async function load() {
  loading.value = true
  try {
    await loadAll()
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  try {
    practiceModes.value = await getPracticeModes()
  } catch {
    practiceModes.value = []
  }
  try {
    personas.value = await getPersonas()
  } catch {
    personas.value = []
  }
  // 有没有一场还没结束的面试？（比如中途点了别的页面）有就给个入口回去继续，
  // 不然用户回到这页只能从头再配一遍
  try {
    const list: any = await listSessions()
    unfinished.value =
      (Array.isArray(list) ? list : [])
        .filter((s: any) => s.status === 1)
        .sort((a: any, b: any) => String(b.start_at || '').localeCompare(String(a.start_at || '')))[0] ||
      null
  } catch {
    unfinished.value = null
  }
  try {
    techDirections.value = await getTechDirections()
  } catch {
    techDirections.value = []
  }
  try {
    targetPositions.value = await listTargetPositions()
    // 只存了一个就直接用它 —— 用户已经在档案页填过一次了，不该再选一次
    if (targetPositions.value.length === 1) {
      selectedTargetPosition.value = targetPositions.value[0].id
    }
  } catch {
    targetPositions.value = []
  }
  // 简历列表：默认选中默认简历，AI 面试官将据此提问
  try {
    const list = await listResumes()
    resumes.value = Array.isArray(list) ? list.filter((r: any) => r.parse_status === 2) : []
    const def = resumes.value.find((r: any) => r.is_default === 1)
    if (def) selectedResume.value = def.id
    // 只有一份可用简历时也直接用它（可能没被标成默认）
    else if (resumes.value.length === 1) selectedResume.value = resumes.value[0].id
  } catch {
    resumes.value = []
  }
  // 默认带入用户在求职档案已选的技术方向
  try {
    const saved = await getUserTechDirections()
    if (Array.isArray(saved)) {
      // 后端返回的字段是 tech_direction_id（不是 id）—— 写错会导致方向永远带不进来
      selectedTechIds.value = saved.map((d: any) => d.tech_direction_id)
    }
  } catch {
    /* 用户未设置技术方向，保持空 */
  }
}

async function handleStart() {
  if (!selectedMode.value) {
    message.warning('请选择练习模式')
    return
  }
  // 全方位面试：技术方向可选，但技术方向/简历/目标岗位至少有其一作为出题依据
  const hasTech = selectedTechIds.value.length > 0 || customTechs.value.length > 0
  const hasPosition = !!selectedTargetPosition.value || !!customPosition.value.trim()
  if (!hasTech && !hasPosition && !selectedResume.value) {
    message.warning('请至少选择技术方向、简历或目标岗位其中一项，作为面试出题依据')
    return
  }
  submitting.value = true
  try {
    const session = await createSession({
      practice_mode_id: selectedMode.value,
      persona_id: selectedPersona.value || undefined,
      // 「按公司定制」时把用户写的风格描述带上；其他情况不带（后端会按岗位自动推导）
      persona_custom: isCustomPersona.value ? (customPersona.value.trim() || undefined) : undefined,
      // 「专项打磨训练」时带上用户指定要练的材料
      focus_target: isFocusedMode.value ? (focusTarget.value || undefined) : undefined,
      tech_direction_ids: selectedTechIds.value.length ? selectedTechIds.value.join(',') : undefined,
      tech_direction_custom: customTechs.value.length ? customTechs.value.join(',') : undefined,
      difficulty: selectedDifficulty.value,
      target_position_id: selectedTargetPosition.value || undefined,
      target_position_custom: customPosition.value.trim() || undefined,
      resume_id: selectedResume.value || undefined,
    })
    const id = session?.id
    if (id) {
      // 记住这次选的方向，下次进来自动带出来（方向只在这一页选，所以要在这里存）
      if (selectedTechIds.value.length) {
        saveUserTechDirections(selectedTechIds.value).catch(() => {})
      }
      message.success('会话已创建，开始面试')
      router.push(`/interview/${id}`)
    } else {
      message.error('创建会话失败，请重试')
    }
  } catch (e: any) {
    const msg: string = e?.message || '创建会话失败，请重试'
    if (msg.includes('次数')) {
      Modal.confirm({
        title: '面试次数不足',
        content: '你的免费/剩余面试次数已用完，可前往会员中心购买次卡或开通不限次会员。',
        okText: '去充值',
        cancelText: '取消',
        onOk: () => router.push('/membership')
      })
    } else {
      message.error(msg)
    }
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="page-head">
      <h2>🎬 面试配置</h2>
      <p class="sub">选择合适的练习模式、技术方向和面试官人设，开启你的模拟面试</p>
    </div>

    <!-- 有一场没结束的面试：给个入口回去继续，不用重新配一遍 -->
    <div v-if="unfinished" class="resume-banner">
      <span class="rb-text">⏸️ 你有一场没结束的面试（{{ unfinishedLabel }}），进度还在。</span>
      <a-button class="btn-coral" @click="router.push(`/interview/${unfinished.id}`)">
        继续这场面试
      </a-button>
    </div>

    <!-- 练习模式 -->
    <div class="section">
      <h3 class="section-title">🎯 选择练习模式 <span class="req">*</span></h3>
      <div v-if="practiceModes.length" class="grid-cards">
        <div
          v-for="m in practiceModes"
          :key="m.id"
          :class="['opt-card', 'mode-card', { selected: selectedMode === m.id }]"
          @click="selectedMode = m.id"
        >
          <div class="opt-emoji">📋</div>
          <div class="opt-name">{{ m.name }}</div>
          <div class="opt-desc">{{ m.description }}</div>
        </div>
      </div>
      <p v-else-if="loading" class="empty-tip">加载中…</p>
      <a-empty v-else description="练习模式暂无数据" />
    </div>

    <!-- 专项打磨训练：指定这次练哪一段 -->
    <div v-if="isFocusedMode" class="section">
      <h3 class="section-title">🎯 这次想练什么？</h3>
      <p class="empty-tip" style="margin-bottom: 12px">
        专项训练只围绕你选的这一段反复深挖，不会跳到别的话题。
        <span v-if="!selectedResume">先在上面选一份简历，就能列出你简历里的项目和实习。</span>
      </p>
      <div v-if="focusOptions.length" class="tech-chips">
        <div
          v-for="opt in focusOptions"
          :key="opt"
          :class="['tech-chip', { selected: focusTarget === opt }]"
          @click="focusTarget = opt"
        >
          {{ opt }}
        </div>
      </div>
      <div class="custom-row" style="margin-top: 12px">
        <a-input
          v-model:value="customFocusInput"
          placeholder="或者自己写，如：蓝桥杯的比赛经历、我的毕业设计"
          @press-enter="useCustomFocus"
        />
        <a-button @click="useCustomFocus">+ 练这个</a-button>
      </div>
      <p v-if="focusTarget" class="picked" style="margin-top: 12px">
        将围绕：<strong>{{ focusTarget }}</strong>
        <a class="link" @click="focusTarget = ''">清除</a>
      </p>
    </div>

    <!-- 面试官人设 -->
    <div class="section">
      <h3 class="section-title">👔 选择面试官人设</h3>
      <div v-if="personas.length" class="grid-cards">
        <div
          v-for="p in personas"
          :key="p.id"
          :class="['opt-card', 'persona-card', { selected: selectedPersona === p.id }]"
          @click="selectedPersona = p.id"
        >
          <div class="opt-emoji">🧠</div>
          <div class="opt-name">{{ p.name }}</div>
          <div class="opt-desc">{{ p.description }}</div>
        </div>
      </div>
      <p v-else-if="loading" class="empty-tip">加载中…</p>
      <a-empty v-else description="面试官人设暂无数据" />

      <!-- 选了「按公司定制」：有目标岗位就自动模仿该公司，没有才让用户自己写一句 -->
      <div v-if="isCustomPersona && !hasPosition" class="custom-row" style="margin-top: 12px">
        <a-input
          v-model:value="customPersona"
          placeholder="描述你希望的面试官风格，如：像字节跳动那样爱追问项目细节和数据"
        />
      </div>
      <p v-else-if="isCustomPersona" class="empty-tip" style="margin-top: 12px">
        已选择目标岗位，将自动模仿该公司的面试风格（无需填写）。
      </p>
    </div>

    <!-- 技术方向 -->
    <div class="section">
      <h3 class="section-title">🧭 选择方向 / 领域（可选）</h3>
      <p class="empty-tip" style="margin-bottom: 12px">
        技术岗选 Java后端、前端、测试等；非技术岗选运营、行政、市场、人力资源等。
        <br />选得越具体，面试官越能围绕这个方向提问；不确定也可以不选，AI 会根据简历和目标岗位判断。
      </p>
      <div v-if="techDirections.length" class="tech-chips">
        <div
          v-for="t in techDirections"
          :key="t.id"
          :class="['tech-chip', { selected: selectedTechIds.includes(t.id) }]"
          @click="toggleTech(t.id)"
        >
          {{ t.name }}
        </div>
      </div>
      <p v-else-if="loading" class="empty-tip">加载中…</p>
      <a-empty v-else description="方向列表暂无数据，可在下方自己输入" />

      <!-- 自定义技术方向 -->
      <div class="custom-row">
        <a-input
          v-model:value="customTechInput"
          placeholder="没有找到？输入自定义方向，如：网络安全、跨境电商、医药代表"
          @press-enter="addCustomTech"
        />
        <a-button @click="addCustomTech">+ 添加方向</a-button>
      </div>
      <div v-if="customTechs.length" class="tech-chips" style="margin-top: 12px">
        <div v-for="t in customTechs" :key="t" class="tech-chip selected custom-chip">
          {{ t }}<span class="chip-x" title="移除" @click="removeCustomTech(t)">×</span>
        </div>
      </div>
    </div>

    <!-- 难度 -->
    <div class="section">
      <h3 class="section-title">📊 面试难度</h3>
      <a-slider
        v-model:value="selectedDifficulty"
        :min="1"
        :max="5"
        :marks="DIFFICULTY_LABELS"
        :step="1"
        style="max-width: 520px"
      />
    </div>

    <!-- 目标岗位 -->
    <div class="section">
      <h3 class="section-title">🎯 目标岗位（可选）</h3>

      <!-- 档案里只存了一个：折成一行，不必再选一次 -->
      <p v-if="targetPositions.length === 1 && !showPositionPicker" class="picked">
        将使用：<strong>{{ positionLabel(targetPositions[0]) }}</strong>
        <a class="link" @click="showPositionPicker = true">更换</a>
      </p>

      <template v-else>
        <a-select
          v-if="targetPositions.length"
          v-model:value="selectedTargetPosition"
          placeholder="选择你已添加的目标岗位"
          style="max-width: 520px; display: block"
          allow-clear
        >
          <a-select-option v-for="tp in targetPositions" :key="tp.id" :value="tp.id">
            {{ positionLabel(tp) }}
          </a-select-option>
        </a-select>
        <p v-else class="empty-tip">
          档案里还没存目标岗位。可在下面直接输入，或去「求职档案」添加
        </p>
        <div class="custom-row" style="margin-top: 12px">
          <a-input
            v-model:value="customPosition"
            placeholder="直接输入，如：Python 后端开发工程师"
            allow-clear
          />
        </div>
      </template>
    </div>

    <!-- 面试简历 -->
    <div class="section">
      <h3 class="section-title">📄 面试简历（可选）</h3>

      <p v-if="resumes.length === 1 && !showResumePicker" class="picked">
        将使用：<strong>{{ resumeLabel(resumes[0]) }}</strong>
        <a class="link" @click="showResumePicker = true">更换</a>
      </p>

      <template v-else>
        <a-select
          v-if="resumes.length"
          v-model:value="selectedResume"
          placeholder="选择简历，面试官将根据简历内容提问"
          style="max-width: 520px; display: block"
          allow-clear
        >
          <a-select-option v-for="r in resumes" :key="r.id" :value="r.id">
            {{ resumeLabel(r) }}
          </a-select-option>
        </a-select>
        <p v-else class="empty-tip">
          还没有能用的简历。去「求职档案」上传；不上传则按方向和岗位出题
        </p>
      </template>
    </div>

    <!-- 操作 -->
    <div class="foot-actions">
      <a-button type="primary" class="btn-coral" size="large" :loading="submitting" @click="handleStart">
        开始面试 →
      </a-button>
    </div>
  </div>
</template>

<style scoped>
.page-head { margin-bottom: 24px; }
.page-head h2 { font-size: 22px; color: #3d3848; margin: 0; }
.page-head .sub { color: #82789a; margin-top: 4px; font-size: 14px; }

/* 有一场没结束的面试时的提醒条 */
.resume-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 24px;
  padding: 14px 20px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(246, 253, 251, .94) 0%, rgba(232, 249, 244, .9) 100%);
  border: 1px solid rgba(60, 205, 182, .3);
  box-shadow: 0 6px 20px rgba(60, 205, 182, .12);
}
.resume-banner .rb-text { color: #28695c; font-size: 14px; font-weight: 500; }

.section { margin-bottom: 28px; }
.section-title { font-size: 16px; color: #3d3848; margin: 0 0 14px; }

/* 档案里只有一项时的一行摘要，省掉一个选择器 */
.picked {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 14px;
  color: #82789a;
}
.picked strong { color: #3d3848; font-weight: 600; }
.link { color: #ff8e7b; cursor: pointer; font-size: 13px; }
.link:hover { text-decoration: underline; }
/* .req / .tech-chips / .tech-chip / .empty-tip 已提取到 src/styles/index.css */

.grid-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.opt-card {
  padding: 24px;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  background: rgba(255, 255, 255, 0.85);
  border: 2px solid transparent;
  box-shadow: 0 4px 16px rgba(140,110,170,0.06);
}
.opt-card:hover { transform: translateY(-3px); box-shadow: 0 10px 26px rgba(140,110,170,0.1); }

.mode-card.selected {
  background: linear-gradient(135deg, #FF8E7B 0%, #FFB4A0 50%, #F2A0B6 100%);
  color: #fff;
  border-color: rgba(255,255,255,0.6);
}
.persona-card.selected {
  background: linear-gradient(135deg, #3CCDB6 0%, #7DE5D2 50%, #5CD9A0 100%);
  color: #fff;
  border-color: rgba(255,255,255,0.6);
}
.mode-card.selected .opt-desc, .persona-card.selected .opt-desc { color: rgba(255,255,255,0.92); }

.opt-emoji { font-size: 34px; margin-bottom: 10px; }
.opt-name { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.opt-desc { font-size: 13px; color: #82789a; line-height: 1.6; }

.custom-chip { display: inline-flex; align-items: center; gap: 6px; }
.chip-x {
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  opacity: 0.85;
}
.chip-x:hover { opacity: 1; color: #FF8E7B; }

.custom-row {
  display: flex;
  gap: 10px;
  max-width: 520px;
  margin-top: 14px;
}

.foot-actions { display: flex; justify-content: center; padding-top: 12px; }
.foot-actions .btn-coral { padding: 10px 32px; font-size: 16px; }

@media (max-width: 760px) {
  .grid-cards { grid-template-columns: 1fr; }
}
</style>
