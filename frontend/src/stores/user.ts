import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, demoLogin as demoLoginApi, getMe, uploadAvatar as uploadAvatarApi, updateProfile as updateProfileApi } from '@/api/auth'

const TOKEN_KEY = 'mock_interview_token'

interface UserInfo {
  id: number
  phone: string
  nickname: string
  avatar_url: string | null
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const userInfo = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  // 头像地址。数据库里存的是后端相对路径（/uploads/xxx.jpg），
  // Vite 已把 /uploads 代理到后端，所以直接用相对路径就行。
  // 不再硬编码 127.0.0.1:8000 —— 那样用手机或别的设备访问时会指向错误的机器。
  const userAvatar = computed(() => userInfo.value?.avatar_url || '')

  async function applyLogin(res: any) {
    token.value = res.token || res.access_token || ''
    if (token.value) {
      localStorage.setItem(TOKEN_KEY, token.value)
    }
    try {
      userInfo.value = await getMe()
    } catch {
      /* ignore */
    }
    return res
  }

  async function login(phone: string, code: string) {
    return applyLogin(await loginApi(phone, code))
  }

  // 演示账号登录：不需要短信，适合面试官/体验者直接看完整流程
  async function loginDemo() {
    return applyLogin(await demoLoginApi())
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      userInfo.value = await getMe()
    } catch {
      logout()
    }
  }

  // 保存后回读服务端验证是否真的生效（同时兼容本地 userInfo 为空的情况）
  async function refreshAndVerify(expect: Partial<UserInfo>) {
    const me: any = await getMe()
    userInfo.value = me
    for (const [k, v] of Object.entries(expect)) {
      if (v !== undefined && me?.[k] !== v) {
        throw new Error('保存未生效，请重试')
      }
    }
    return me
  }

  async function updateAvatar(file: File) {
    const res: any = await uploadAvatarApi(file)
    const expected = res?.avatar_url
    // 回读验证：确认服务端已保存新头像，失败抛错（界面保持旧值）
    await refreshAndVerify(expected ? { avatar_url: expected } : {})
    return res
  }

  async function updateNickname(nickname: string) {
    const res: any = await updateProfileApi(nickname)
    // 回读验证：确认服务端已保存新昵称
    await refreshAndVerify({ nickname: res?.nickname || nickname })
    return res
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return { token, userInfo, userAvatar, isLoggedIn, login, loginDemo, fetchMe, updateAvatar, updateNickname, logout }
})
