import axios, { type AxiosRequestConfig } from 'axios'
import { message } from 'ant-design-vue'

const TOKEN_KEY = 'mock_interview_token'
const AUTH_ERROR_KEYWORDS = ['token', '登录', '用户不存在', '已被禁用', 'Signature', 'unauthorized', ' expired']

function isAuthError(msg: string): boolean {
  if (!msg) return false
  const lower = msg.toLowerCase()
  return AUTH_ERROR_KEYWORDS.some(k => lower.includes(k.toLowerCase()))
}

function clearAuthAndRedirect() {
  localStorage.removeItem(TOKEN_KEY)
  const current = window.location.hash + window.location.pathname
  if (!current.includes('/login')) {
    message.warning('登录已过期，请重新登录')
    window.location.href = '/login'
  }
}

const instance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000
})

instance.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  (resp) => {
    const data = resp.data
    if (data && typeof data === 'object' && 'code' in data) {
      if (data.code === 0 || data.code === 200) {
        return data.data
      }
      // 鉴权类错误：清 token 跳登录
      if (isAuthError(data.msg)) {
        clearAuthAndRedirect()
        return Promise.reject(new Error(data.msg))
      }
      message.error(data.msg || '请求失败')
      return Promise.reject(new Error(data.msg || '请求失败'))
    }
    return data
  },
  (err) => {
    const status = err?.response?.status
    const msg = err?.response?.data?.msg || err?.message || '网络错误'
    // HTTP 401/403 或鉴权类错误：清 token 跳登录
    if (status === 401 || status === 403 || isAuthError(msg)) {
      clearAuthAndRedirect()
    } else {
      message.error(msg)
    }
    return Promise.reject(err)
  }
)

// 后端统一返回 {code,data,msg}，响应拦截器已经解包成 data。
// 这里把返回类型显式标成 Promise<T>，避免调用方把 AxiosResponse 当成业务数据。
const request = {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.get(url, config) as unknown as Promise<T>
  },
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return instance.post(url, data, config) as unknown as Promise<T>
  },
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return instance.put(url, data, config) as unknown as Promise<T>
  },
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.delete(url, config) as unknown as Promise<T>
  }
}

export default request
