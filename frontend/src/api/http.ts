import axios, { AxiosError } from 'axios'

import type { ApiError } from '@/types'

export const TOKEN_KEY = 'fleet_token'

/** 401 回调由 main.ts 注入，避免 http ↔ router/store 循环依赖 */
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

export const http = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
  withCredentials: true,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<ApiError>) => {
    const status = error.response?.status
    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      onUnauthorized?.()
    }
    const detail =
      error.response?.data?.detail ||
      (error.code === 'ECONNABORTED' ? '请求超时，请重试' : '') ||
      (status ? `请求失败（${status}）` : '网络异常，请检查网络后重试')
    return Promise.reject(new Error(detail))
  },
)

/** 统一解包 { data: ... } 响应 */
export async function unwrap<T>(p: Promise<{ data: T }>): Promise<T> {
  const r = await p
  return r.data
}
