<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

const props = defineProps<{
  role: 'ai' | 'user'
  text: string
  time?: string
  interviewerAvatar?: string
}>()

const userStore = useUserStore()

const userAvatarUrl = computed(() => userStore.userAvatar)
</script>

<template>
  <div :class="['bubble-row', role]">
    <!-- AI 头像 -->
    <div v-if="role === 'ai'" class="avatar ai-avatar">
      <img :src="interviewerAvatar || '/images/interviewer_digital.svg?v=1'" alt="面试官" />
    </div>
    <!-- 用户头像（动态） -->
    <div v-else class="avatar user-avatar">
      <img v-if="userAvatarUrl" :src="userAvatarUrl" alt="我的头像" />
      <span v-else>我</span>
    </div>
    <div class="bubble-main">
      <div v-if="role === 'ai'" class="bubble-name">面试官</div>
      <div class="bubble-text">{{ text }}</div>
      <div v-if="time" class="bubble-time">{{ time }}</div>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  gap: 12px;
  margin: 16px 0;
  align-items: flex-start;
}
.bubble-row.user {
  flex-direction: row-reverse;
}
.avatar {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
}
.ai-avatar {
  border: 2px solid #B49EE8;
  box-shadow: 0 4px 12px rgba(180, 158, 232, 0.35);
}
.user-avatar {
  background: linear-gradient(135deg, #F2A0B6 0%, #FFB4A0 100%);
  color: #fff;
  font-weight: 700;
  font-size: 15px;
  box-shadow: 0 4px 12px rgba(242, 160, 182, 0.35);
  border: 2px solid rgba(255, 180, 160, 0.6);
}
.bubble-main {
  max-width: 70%;
}
.bubble-name {
  font-size: 12px;
  color: #82789a;
  margin-bottom: 4px;
  font-weight: 500;
}
.bubble-text {
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
}
.bubble-row.ai .bubble-text {
  background: rgba(236, 228, 252, 0.55);
  color: #3d3848;
  border: 1px solid rgba(212, 200, 240, 0.5);
  border-top-left-radius: 4px;
}
.bubble-row.user .bubble-text {
  background: linear-gradient(135deg, #FF8E7B 0%, #FFB4A0 50%, #F2A0B6 100%);
  color: #fff;
  border-top-right-radius: 4px;
  box-shadow: 0 6px 16px rgba(255, 142, 123, 0.3);
}
.bubble-time {
  font-size: 12px;
  color: #82789a;
  margin-top: 4px;
}
.bubble-row.user .bubble-time {
  text-align: right;
}
</style>
