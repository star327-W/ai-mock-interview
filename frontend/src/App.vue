<script setup lang="ts">
import AppBackground from '@/components/AppBackground.vue'
</script>

<template>
  <div class="app-root">
    <AppBackground />
    <div class="app-content">
      <router-view />
    </div>
  </div>
</template>

<style>
.app-root {
  position: relative;
  min-height: 100vh;
  width: 100%;
}
.app-content {
  position: relative;
  z-index: 1;
}
</style>
