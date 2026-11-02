<script setup lang="ts">
import NavBar from './NavBar.vue'
</script>

<template>
  <div class="app-layout">
    <NavBar />
    <div class="app-layout-content">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  background: transparent;
  position: relative;
  z-index: 1;
  pointer-events: auto;
}
.app-layout-content {
  padding-top: 72px;
  position: relative;
  z-index: 1;
  pointer-events: auto;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
