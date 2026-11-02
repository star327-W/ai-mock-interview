<script setup lang="ts">
// 全屏动态光圈背景组件：纯 CSS 渐变 + 动画实现流星 + 星点 + 漂移光晕
const starPositions: Array<{ top: string; left: string; color: string; delay: string }> = [
  { top: '12%', left: '22%', color: '#FF8E7B', delay: '0s' },
  { top: '18%', left: '60%', color: '#3CCDB6', delay: '1s' },
  { top: '30%', left: '80%', color: '#F5C950', delay: '2s' },
  { top: '45%', left: '15%', color: '#B49EE8', delay: '0.5s' },
  { top: '55%', left: '40%', color: '#F2A0B6', delay: '1.5s' },
  { top: '65%', left: '70%', color: '#5CD9A0', delay: '2.5s' },
  { top: '72%', left: '28%', color: '#6BAEEA', delay: '1.2s' },
  { top: '80%', left: '88%', color: '#F5A86A', delay: '3s' },
  { top: '88%', left: '55%', color: '#FF8E7B', delay: '0.8s' },
  { top: '92%', left: '12%', color: '#B49EE8', delay: '1.8s' }
]
</script>

<template>
  <div class="app-bg">
    <div class="orb-1"></div>
    <div class="orb-2"></div>
    <div class="orb-3"></div>
    <div class="orb-4"></div>
    <div class="orb-5"></div>

    <div class="shooting-star ss-1"></div>
    <div class="shooting-star ss-2"></div>
    <div class="shooting-star ss-3"></div>
    <div class="shooting-star ss-4"></div>
    <div class="shooting-star ss-5"></div>

    <div
      v-for="(s, i) in starPositions"
      :key="i"
      class="star-dot"
      :style="{ top: s.top, left: s.left, color: s.color, animationDelay: s.delay }"
    ></div>
  </div>
</template>
