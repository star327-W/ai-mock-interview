import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'

const routes: RouteRecordRaw[] = [
  { path: '/login', component: () => import('@/views/Login.vue'), meta: { noAuth: true } },
  {
    path: '/',
    component: AppLayout,
    redirect: '/home',
    children: [
      { path: 'home', name: 'Home', component: () => import('@/views/Home.vue'), meta: { title: '首页' } },
      { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue'), meta: { title: '求职档案' } },
      { path: 'interview/config', name: 'InterviewConfig', component: () => import('@/views/InterviewConfig.vue'), meta: { title: '面试配置' } },
      { path: 'interview/:id', name: 'Interview', component: () => import('@/views/Interview.vue'), meta: { title: '面试中' } },
      { path: 'report/:sessionId', name: 'Report', component: () => import('@/views/Report.vue'), meta: { title: '评估报告' } },
      { path: 'growth', name: 'Growth', component: () => import('@/views/Growth.vue'), meta: { title: '成长追踪' } },
      { path: 'community', name: 'Community', component: () => import('@/views/Community.vue'), meta: { title: '面经社区' } },
      { path: 'membership', name: 'Membership', component: () => import('@/views/Membership.vue'), meta: { title: '会员中心' } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/home' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('mock_interview_token')
  if (to.meta.noAuth) {
    if (token) return '/home'
    return true
  }
  if (!token) {
    return '/login'
  }
  return true
})

export default router
