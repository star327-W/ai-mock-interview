<script lang="ts">
/** 清单项：由使用方（页面）算好传进来，组件本身不碰任何接口 */
export interface ChecklistItem {
  key: string
  label: string
  hint?: string
  done: boolean
  /** 默认 true。false = 可选项，不计入完成度分母 */
  required?: boolean
  /** 点击后要滚动到的区块 DOM id，如 'sec-resume' */
  target: string
}
</script>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    items: ChecklistItem[]
    title?: string
    desc?: string
  }>(),
  {
    title: '完善求职档案',
    desc: '按下面几项补齐，AI 面试官才能问得更准'
  }
)

const emit = defineEmits<{ (e: 'jump', item: ChecklistItem): void }>()

// 只有必填项计入分母 —— 昵称头像这种装饰性的不该卡住"100%"
const requiredItems = computed(() => props.items.filter((i) => i.required !== false))
const doneCount = computed(() => requiredItems.value.filter((i) => i.done).length)
const total = computed(() => requiredItems.value.length)
const percent = computed(() =>
  total.value ? Math.round((doneCount.value / total.value) * 100) : 0
)
const allDone = computed(() => total.value > 0 && doneCount.value === total.value)
</script>

<template>
  <div class="glass-card cl-card" :class="{ 'all-done': allDone }">
    <div class="cl-head">
      <div>
        <h3 class="cl-title">{{ title }}</h3>
        <p class="cl-desc">{{ desc }}</p>
      </div>
      <div class="cl-count">{{ doneCount }}<span>/{{ total }}</span></div>
    </div>

    <a-progress
      :percent="percent"
      :show-info="false"
      :stroke-color="
        allDone
          ? { '0%': '#3CCDB6', '100%': '#7DE5D2' }
          : { '0%': '#ff8e7b', '100%': '#f2a0b6' }
      "
      :trail-color="'rgba(140,110,170,0.12)'"
    />

    <div class="cl-list">
      <div
        v-for="it in items"
        :key="it.key"
        class="cl-item"
        :class="{ done: it.done, optional: it.required === false }"
        @click="emit('jump', it)"
      >
        <span class="cl-box">{{ it.done ? '✓' : '' }}</span>
        <span class="cl-label">{{ it.label }}</span>
        <span v-if="it.hint && !it.done" class="cl-hint">{{ it.hint }}</span>
        <span v-if="it.required === false" class="cl-opt">可选</span>
        <span v-else-if="!it.done" class="cl-go">去完成</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cl-card { padding: 22px 24px; }

.cl-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.cl-title { margin: 0; font-size: 17px; color: #3d3848; }
.cl-desc { margin: 4px 0 0; font-size: 13px; color: #82789a; }

.cl-count {
  font-size: 26px;
  font-weight: 700;
  color: #ff8e7b;
  line-height: 1;
  white-space: nowrap;
}
.cl-count span { font-size: 14px; color: #82789a; font-weight: 500; }
.cl-card.all-done .cl-count { color: #3ccdb6; }

.cl-list { margin-top: 14px; display: flex; flex-direction: column; gap: 2px; }

.cl-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 8px;
  font-size: 14px;
  color: #3d3848;
  transition: background 0.15s;
}
.cl-item:not(.done) { cursor: pointer; }
.cl-item:not(.done):hover { background: rgba(255, 142, 123, 0.08); }
.cl-item.optional { color: #82789a; }

.cl-box {
  width: 18px;
  height: 18px;
  flex: none;
  border-radius: 5px;
  border: 1.5px solid #d4c8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #fff;
}
.cl-item.done .cl-box {
  background: linear-gradient(135deg, #3ccdb6, #7de5d2);
  border-color: transparent;
}

.cl-hint { font-size: 12px; color: #a79fbb; }
.cl-opt,
.cl-go { margin-left: auto; font-size: 12px; flex: none; }
.cl-opt { color: #a79fbb; }
.cl-go { color: #ff8e7b; font-weight: 600; }
</style>
