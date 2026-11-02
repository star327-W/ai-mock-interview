<script setup lang="ts">
defineProps<{
  active?: boolean
  bars?: number
}>()
</script>

<template>
  <div class="waveform">
    <span
      v-for="i in (bars || 28)"
      :key="i"
      class="wave-bar"
      :style="{ animationDelay: `${(i % 10) * 0.08}s` }"
    ></span>
  </div>
</template>

<style scoped>
.waveform {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 40px;
  padding: 0 8px;
}
.wave-bar {
  width: 4px;
  height: 12px;
  border-radius: 3px;
  background: linear-gradient(180deg, #FF8E7B 0%, #F2A0B6 100%);
  animation: wavePulse 1s ease-in-out infinite;
}
@keyframes wavePulse {
  0%, 100% { transform: scaleY(0.3); }
  50% { transform: scaleY(1.5); }
}
</style>
