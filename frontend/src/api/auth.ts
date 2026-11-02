import request from './request'

export function sendSmsCode(phone: string, scene = 'LOGIN') {
  return request.post('/auth/sms/send', { phone, scene })
}

export function login(phone: string, code: string) {
  return request.post('/auth/login', { phone, code })
}

// 演示账号一键登录：不需要手机号和短信，面试官/体验者用
export function demoLogin() {
  return request.post('/auth/demo-login')
}

export function getMe() {
  return request.get('/auth/me')
}

export function uploadAvatar(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return request.put('/auth/avatar', fd, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function updateProfile(nickname: string) {
  return request.put('/auth/profile', { nickname })
}
