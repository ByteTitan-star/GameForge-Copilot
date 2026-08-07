import { env } from '@/lib/env'
import { useAuthStore } from '@/stores/auth-store'
import { ApiError } from './errors'
import type { ApiErrorBody, ApiListSuccess } from './types'

type RequestOptions = {
  method?: string
  body?: unknown
  token?: string | null
  signal?: AbortSignal
  /** 内部：已做过一次 refresh 重试，避免死循环 */
  _retried?: boolean
}

function buildHeaders(options: RequestOptions): Record<string, string> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.token) headers.Authorization = `Bearer ${options.token}`
  return headers
}

async function parseError(res: Response): Promise<never> {
  const json = (await res.json().catch(() => null)) as ApiErrorBody | null
  const errBody =
    json && 'error' in json && json.error
      ? json.error
      : { code: 'UNKNOWN', message: res.statusText || 'Request failed' }
  throw new ApiError(res.status, errBody)
}

async function maybeRefresh(options: RequestOptions): Promise<string | null> {
  if (options._retried) return null
  const store = useAuthStore.getState()
  const refresh = store.refresh_token
  const user = store.user
  if (!refresh || !user) return null
  try {
    // 动态 import 避免 client ↔ auth 循环依赖
    const { authApi } = await import('./auth')
    const tokens = await authApi.refresh(refresh)
    store.setSession({
      user,
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
    })
    return tokens.access_token
  } catch {
    store.clearSession()
    return null
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const res = await fetch(`${env.apiBaseUrl}${path}`, {
    method: options.method ?? 'GET',
    headers: buildHeaders(options),
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })

  if (res.status === 401 && options.token) {
    const next = await maybeRefresh(options)
    if (next) {
      return apiRequest<T>(path, { ...options, token: next, _retried: true })
    }
  }

  if (!res.ok) await parseError(res)

  const json = (await res.json().catch(() => null)) as { data: T } | null
  if (!json || !('data' in json)) {
    throw new ApiError(500, { code: 'UNKNOWN', message: 'Invalid response shape' })
  }
  return json.data
}

/** 204 / 空体成功（如 logout） */
export async function apiRequestNoContent(path: string, options: RequestOptions = {}): Promise<void> {
  const res = await fetch(`${env.apiBaseUrl}${path}`, {
    method: options.method ?? 'POST',
    headers: buildHeaders(options),
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })
  if (res.status === 204) return
  if (res.status === 401 && options.token) {
    const next = await maybeRefresh(options)
    if (next) {
      return apiRequestNoContent(path, { ...options, token: next, _retried: true })
    }
  }
  if (!res.ok) await parseError(res)
}

export async function apiRequestList<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiListSuccess<T>> {
  const res = await fetch(`${env.apiBaseUrl}${path}`, {
    method: options.method ?? 'GET',
    headers: buildHeaders(options),
    signal: options.signal,
  })
  if (res.status === 401 && options.token) {
    const next = await maybeRefresh(options)
    if (next) {
      return apiRequestList<T>(path, { ...options, token: next, _retried: true })
    }
  }
  if (!res.ok) await parseError(res)

  const json = (await res.json().catch(() => null)) as ApiListSuccess<T> | { data: T[] } | null
  if (!json || !('data' in json) || !Array.isArray(json.data)) {
    throw new ApiError(500, { code: 'UNKNOWN', message: 'Invalid list response shape' })
  }
  const data = json.data
  return {
    data,
    total: 'total' in json && json.total != null ? Number(json.total) : data.length,
    page: 'page' in json && json.page != null ? Number(json.page) : 1,
    size: 'size' in json && json.size != null ? Number(json.size) : data.length,
  }
}
