<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import { UploadOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import {
  listResumes,
  uploadResume,
  deleteResume,
  setDefaultResume,
  listTargetPositions,
  createTargetPosition,
  deleteTargetPosition
} from '@/api/resume'
import CompletionChecklist from '@/components/CompletionChecklist.vue'

const router = useRouter()

const loading = ref(true)
const saving = ref(false)

const resumes = ref<any[]>([])
const positions = ref<any[]>([])

const posForm = reactive({
  company_name: '',
  position_name: '',
  job_desc: ''
})

// parse_status 数字 → 文案
const PARSE_STATUS_MAP: Record<number, { text: string; color: string }> = {
  0: { text: '待解析', color: 'orange' },
  1: { text: '解析中', color: 'blue' },
  2: { text: '已解析', color: 'green' },
  3: { text: '解析失败', color: 'red' }
}

// 完成度清单：这一页只负责"存材料"，方向/难度等留给面试配置页
const checklist = computed(() => [
  {
    key: 'resume',
    label: '上传一份简历',
    hint: '面试官据此提问',
    done: resumes.value.length > 0,
    required: true,
    target: 'sec-resume'
  },
  {
    key: 'position',
    label: '添加目标岗位',
    hint: '面试官围绕它出题',
    done: positions.value.length > 0,
    required: true,
    target: 'sec-position'
  }
])

const doneRequired = computed(() => checklist.value.filter((i) => i.done).length)

async function load() {
  loading.value = true
  try {
    try { resumes.value = await listResumes() } catch { resumes.value = [] }
    try { positions.value = await listTargetPositions() } catch { positions.value = [] }
  } finally {
    loading.value = false
  }
}

// 从清单跳到对应区块：滚动 + 闪一下，让用户知道"就是这块"
function onJump(item: { done?: boolean; target: string }) {
  if (item.done) return
  const el = document.getElementById(item.target)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  el.classList.add('flash-highlight')
  window.setTimeout(() => el.classList.remove('flash-highlight'), 1200)
}

// ---- 简历 ----
async function handleUpload({ file, onSuccess, onError }: {
  file: File
  onSuccess?: (ret?: any) => void
  onError?: (err?: any) => void
}) {
  try {
    // 第一份简历自动设为默认，面试时才不用再挑
    const res: any = await uploadResume(file, resumes.value.length === 0 ? 1 : 0)
    message.success(res?.message || '简历上传成功')
    await load()
    onSuccess?.({})
  } catch (e) {
    onError?.(e)
  }
  return false
}

async function handleSetDefault(id: number) {
  try {
    await setDefaultResume(id)
    message.success('已设为默认简历')
    await load()
  } catch {
    /* 错误提示由请求拦截器统一处理 */
  }
}

function handleDeleteResume(r: any) {
  Modal.confirm({
    title: '删除这份简历？',
    content: r.file_name,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteResume(r.id)
      message.success('已删除')
      await load()
    }
  })
}

// ---- 目标岗位 ----
async function handleAddPosition() {
  if (!posForm.position_name.trim()) {
    message.warning('请填写目标岗位')
    return
  }
  await createTargetPosition(posForm)
  message.success('已添加目标岗位')
  posForm.company_name = ''
  posForm.position_name = ''
  posForm.job_desc = ''
  await load()
}

function handleDeletePosition(p: any) {
  Modal.confirm({
    title: '删除这个目标岗位？',
    content: p.position_name,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteTargetPosition(p.id)
      message.success('已删除')
      await load()
    }
  })
}

// ---- 下一步：至少存了一样材料就放行 ----
function goNext() {
  if (saving.value) return
  if (doneRequired.value === 0) {
    message.warning('先上传简历或添加目标岗位，面试官才有材料可问')
    onJump({ done: false, target: 'sec-resume' })
    return
  }
  router.push('/interview/config')
}

onMounted(load)
</script>

<template>
  <div class="page-container profile-page">
    <header class="page-head">
      <h2>💼 求职档案</h2>
      <p class="sub">把材料存在这儿，面试时直接调用</p>
    </header>

    <CompletionChecklist
      :items="checklist"
      title="准备面试材料"
      desc="存一次，每次面试都能用"
    />

    <!-- 简历 -->
    <section id="sec-resume" class="glass-card sec-card">
      <div class="sec-head">
        <h3 class="sec-title">📄 简历</h3>
        <span class="sec-badge">必填</span>
      </div>
      <p class="sec-desc">上传后自动读取内容，面试官据此提问</p>

      <a-upload-dragger
        :show-upload-list="false"
        :custom-request="handleUpload"
        accept=".pdf,.doc,.docx,.txt"
      >
        <p class="ant-upload-drag-icon">
          <UploadOutlined style="font-size: 40px; color: #FF8E7B;" />
        </p>
        <p class="ant-upload-text">点击或拖拽简历到此处上传</p>
        <p class="ant-upload-hint">PDF / Word / TXT</p>
      </a-upload-dragger>

      <div v-if="loading" class="empty-block">加载中…</div>
      <div v-else-if="resumes.length" class="resume-list">
        <div v-for="r in resumes" :key="r.id" class="resume-item">
          <div class="resume-info">
            <div class="resume-name">📄 {{ r.file_name }}</div>
            <div class="resume-meta">
              <a-tag :color="(PARSE_STATUS_MAP[r.parse_status] || {}).color || 'default'">
                {{ (PARSE_STATUS_MAP[r.parse_status] || {}).text || '已上传' }}
              </a-tag>
              <span v-if="r.is_default" class="default-tag">默认简历</span>
              <span v-else class="set-default" @click="handleSetDefault(r.id)">设为默认</span>
              <span v-if="r.parse_status === 3" class="parse-warn">
                没读出文字，换 TXT 或 PDF 再传一次
              </span>
            </div>
          </div>
          <a-button type="text" danger @click="handleDeleteResume(r)">
            <DeleteOutlined /> 删除
          </a-button>
        </div>
      </div>
      <p v-else class="empty-block">还没有简历，把文件拖到上面那块区域</p>
    </section>

    <!-- 目标岗位 -->
    <section id="sec-position" class="glass-card sec-card">
      <div class="sec-head">
        <h3 class="sec-title">🎯 目标岗位</h3>
        <span class="sec-badge">必填</span>
      </div>
      <p class="sec-desc">填上你要投的岗位，面试官围绕它的要求出题</p>

      <a-form layout="vertical" class="pos-form">
        <div class="pos-row">
          <a-form-item label="公司">
            <a-input v-model:value="posForm.company_name" placeholder="如：字节跳动" />
          </a-form-item>
          <a-form-item label="岗位" required>
            <a-input v-model:value="posForm.position_name" placeholder="如：后端开发工程师" />
          </a-form-item>
        </div>
        <a-form-item label="岗位要求（可选）">
          <a-textarea
            v-model:value="posForm.job_desc"
            :rows="3"
            placeholder="一行一条，面试官会往这些点上问"
          />
        </a-form-item>
        <a-button class="btn-coral" @click="handleAddPosition">添加</a-button>
      </a-form>

      <div v-if="positions.length" class="pos-list">
        <div v-for="p in positions" :key="p.id" class="pos-item">
          <div>
            <div class="pos-title">
              <span class="grad-coral chip">{{ p.position_name }}</span>
              <span v-if="p.company_name" class="chip chip-turquoise">{{ p.company_name }}</span>
            </div>
            <div v-if="p.job_desc" class="pos-desc">{{ p.job_desc }}</div>
          </div>
          <a-button type="text" danger @click="handleDeletePosition(p)">
            <DeleteOutlined />
          </a-button>
        </div>
      </div>
      <p v-else-if="!loading" class="empty-block">还没添加目标岗位，填上面的表单就行</p>
    </section>

    <!-- 下一步 -->
    <div class="foot-actions sticky">
      <span class="foot-tip">已准备 <strong>{{ doneRequired }}/2</strong> 项材料</span>
      <a-button class="btn-coral" size="large" @click="goNext">去配置面试 →</a-button>
    </div>
  </div>
</template>

<style scoped>
/* 通用区块样式在 src/styles/index.css，这里只留本页私有部分 */

.resume-list { margin-top: 16px; display: flex; flex-direction: column; gap: 10px; }
.resume-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-radius: 10px;
  background: rgba(140, 110, 170, 0.05);
}
.resume-name { font-weight: 600; color: #3d3848; }
.resume-meta {
  margin-top: 4px;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.default-tag { font-size: 12px; color: #ff8e7b; }
.set-default { font-size: 12px; color: #82789a; cursor: pointer; }
.set-default:hover { color: #ff8e7b; text-decoration: underline; }
.parse-warn { font-size: 12px; color: #e08a3c; }

.pos-form { margin-bottom: 20px; }
.pos-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.pos-list { display: flex; flex-direction: column; gap: 12px; }
.pos-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(140, 110, 170, 0.05);
}
.pos-title { display: flex; gap: 8px; margin-bottom: 6px; }
.chip { color: #fff; padding: 2px 10px; border-radius: 10px; font-size: 12px; }
.chip-turquoise { background: linear-gradient(135deg, #3ccdb6 0%, #7de5d2 100%); }
.pos-desc { font-size: 13px; color: #82789a; line-height: 1.6; white-space: pre-line; }

@media (max-width: 760px) {
  .pos-row { grid-template-columns: 1fr; }
}
</style>
