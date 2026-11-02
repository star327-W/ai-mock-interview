<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { UserOutlined, LogoutOutlined, HomeOutlined, EditOutlined, LineChartOutlined, TeamOutlined, ExperimentOutlined, SolutionOutlined, CrownOutlined } from '@ant-design/icons-vue'
import { useUserStore } from '@/stores/user'
import ProfileEditModal from './ProfileEditModal.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 头像/昵称的修改走弹窗，不占页面区块
const editProfileOpen = ref(false)

// 全局兜底：任何页面刷新后都拉一次用户信息，保证昵称/头像最新
onMounted(() => {
  if (!userStore.userInfo && userStore.isLoggedIn) {
    userStore.fetchMe()
  }
})

const menus = [
  { path: '/home', label: '首页', icon: HomeOutlined },
  { path: '/profile', label: '求职档案', icon: SolutionOutlined },
  { path: '/interview/config', label: '开始面试', icon: ExperimentOutlined },
  { path: '/growth', label: '成长追踪', icon: LineChartOutlined },
  { path: '/community', label: '面经社区', icon: TeamOutlined },
  { path: '/membership', label: '会员中心', icon: CrownOutlined }
]

function isActive(p: string) {
  return route.path === p || (p !== '/home' && route.path.startsWith(p))
}

function go(p: string) {
  router.push(p)
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <header class="nav-bar">
    <div class="nav-inner">
      <div class="nav-logo" @click="go('/home')">
        <div class="logo-icon">🎙️</div>
        <div class="logo-text">
          <div class="logo-title">模拟面试AI助手</div>
          <div class="logo-sub">Mock Interview AI</div>
        </div>
      </div>

      <nav class="nav-menu">
        <div
          v-for="m in menus"
          :key="m.path"
          :class="['nav-item', { active: isActive(m.path) }]"
          @click="go(m.path)"
        >
          <component :is="m.icon" />
          <span>{{ m.label }}</span>
        </div>
      </nav>

      <div class="nav-user">
        <a-dropdown>
          <div class="user-trigger">
            <div class="avatar">
              <img v-if="userStore.userAvatar" :src="userStore.userAvatar" alt="头像" />
              <UserOutlined v-else />
            </div>
            <span class="nick">{{ userStore.userInfo?.nickname || '用户' }}</span>
          </div>
          <template #overlay>
            <a-menu>
              <a-menu-item key="edit" @click="editProfileOpen = true">
                <EditOutlined /> 修改资料
              </a-menu-item>
              <a-menu-item key="profile" @click="go('/profile')">
                <SolutionOutlined /> 求职档案
              </a-menu-item>
              <a-menu-divider />
              <a-menu-item key="logout" @click="handleLogout">
                <LogoutOutlined /> 退出登录
              </a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </div>

    <ProfileEditModal v-model:open="editProfileOpen" />
  </header>
</template>

<style scoped>
.nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  z-index: 100;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.5);
}
.nav-inner {
  max-width: 1280px;
  height: 100%;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 32px;
}
.nav-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.logo-icon {
  font-size: 26px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #FF8E7B 0%, #FFB4A0 50%, #F2A0B6 100%);
  box-shadow: 0 4px 14px rgba(255, 142, 123, 0.35);
}
.logo-title { font-size: 16px; font-weight: 700; color: #3d3848; }
.logo-sub { font-size: 11px; color: #82789a; letter-spacing: 0.5px; }

.nav-menu {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  justify-content: center;
}
.nav-item {
  padding: 8px 16px;
  border-radius: 10px;
  color: #82789a;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.15s;
}
.nav-item:hover { color: #3d3848; background: rgba(255,255,255,0.5); }
.nav-item.active {
  color: #FF8E7B;
  background: rgba(255, 180, 160, 0.25);
  font-weight: 600;
}

.nav-user { margin-left: auto; }
.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 20px;
  transition: background 0.15s;
}
.user-trigger:hover { background: rgba(255,255,255,0.5); }
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #B49EE8 0%, #D4C8F0 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  overflow: hidden;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.nick { font-size: 14px; color: #3d3848; font-weight: 500; }
</style>
