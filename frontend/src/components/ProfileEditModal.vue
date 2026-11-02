<script setup lang="ts">
/**
 * 修改资料弹窗：头像 + 昵称（手机号是登录账号，只读）。
 * 从导航栏头像的下拉菜单进入 —— 这类"身份设置"不该占一个页面区块。
 */
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { EditOutlined } from '@ant-design/icons-vue'
import { useUserStore } from '@/stores/user'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()

const userStore = useUserStore()

const editingNickname = ref(false)
const nicknameInput = ref('')
const uploadingAvatar = ref(false)
const savingNickname = ref(false)

// 每次打开都回到"非编辑"状态
watch(
  () => props.open,
  (v) => {
    if (v) editingNickname.value = false
  }
)

function close() {
  emit('update:open', false)
}

async function handleAvatarUpload({ file }: any) {
  uploadingAvatar.value = true
  try {
    await userStore.updateAvatar(file)
    message.success('头像已更新')
  } catch (e: any) {
    message.error(e?.message || '头像上传失败，请重试')
  }
  uploadingAvatar.value = false
  return false
}

function startEditNickname() {
  nicknameInput.value = userStore.userInfo?.nickname || ''
  editingNickname.value = true
}

async function saveNickname() {
  const name = nicknameInput.value.trim()
  if (!name) {
    message.warning('昵称不能为空')
    return
  }
  if (savingNickname.value) return
  savingNickname.value = true
  try {
    await userStore.updateNickname(name)
    message.success('昵称已更新')
    editingNickname.value = false
  } catch (e: any) {
    // 失败保持编辑态，方便直接重试
    message.error(e?.message || '昵称保存失败，请重试')
  } finally {
    savingNickname.value = false
  }
}
</script>

<template>
  <a-modal
    :open="open"
    title="修改资料"
    :footer="null"
    :width="400"
    @cancel="close"
  >
    <div class="edit-row">
      <a-upload
        :show-upload-list="false"
        :custom-request="handleAvatarUpload"
        accept="image/*"
        :disabled="uploadingAvatar"
      >
        <div class="avatar">
          <img v-if="userStore.userAvatar" :src="userStore.userAvatar" alt="头像" />
          <span v-else class="ph">{{ (userStore.userInfo?.nickname || '我').charAt(0) }}</span>
          <div class="mask">
            <EditOutlined />
            <span>换头像</span>
          </div>
        </div>
      </a-upload>

      <div class="fields">
        <div class="field">
          <label>昵称</label>
          <template v-if="editingNickname">
            <a-input
              v-model:value="nicknameInput"
              size="small"
              style="width: 140px"
              @press-enter="saveNickname"
            />
            <a-button size="small" class="btn-coral" :loading="savingNickname" @click="saveNickname">
              保存
            </a-button>
            <a-button size="small" @click="editingNickname = false">取消</a-button>
          </template>
          <template v-else>
            <span class="val">{{ userStore.userInfo?.nickname || '用户' }}</span>
            <a-button type="text" size="small" @click="startEditNickname">
              <EditOutlined /> 修改
            </a-button>
          </template>
        </div>

        <div class="field">
          <label>手机号</label>
          <span class="val muted">{{ userStore.userInfo?.phone || '—' }}</span>
          <span class="tip">登录账号，不可修改</span>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<style scoped>
.edit-row { display: flex; gap: 20px; align-items: flex-start; }

.avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  overflow: hidden;
  position: relative;
  cursor: pointer;
  border: 2px solid rgba(255, 142, 123, 0.3);
  transition: border-color 0.2s;
}
.avatar:hover { border-color: #ff8e7b; }
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.ph {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #ff8e7b, #f2a0b6);
  color: #fff;
  font-size: 28px;
  font-weight: 700;
}
.mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-size: 11px;
  opacity: 0;
  transition: opacity 0.2s;
  border-radius: 50%;
}
.avatar:hover .mask { opacity: 1; }

.fields { flex: 1; display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.field label { width: 48px; flex: none; font-size: 13px; color: #82789a; }
.val { font-size: 14px; color: #3d3848; font-weight: 500; }
.val.muted { font-weight: 400; color: #6f6685; }
.tip { font-size: 12px; color: #a79fbb; }
</style>
