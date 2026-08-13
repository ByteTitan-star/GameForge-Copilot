import { env } from '@/lib/env'
import { useAuthStore } from '@/stores/auth-store'
import { ApiError } from './errors'
import type { ApiErrorBody, ApiListSuccess } from './types'

type RequestOptions = {
  method?: string
  body?: unknown
  token?: string | null
  signal?: AbortSignal
  headers?: Record<string, string>
  /** 内部：已做过一次 refresh 重试，避免死循环 */
  _retried?: boolean
}

function buildHeaders(options: RequestOptions): Record<string, string> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.token) headers.Authorization = `Bearer ${options.token}`
  return { ...headers, ...options.headers }
}

async function parseError(res: Response): Promise<never> {
  const json = (await res.json().catch(() => null)) as ApiErrorBody | null
  let errBody =
    json && 'error' in json && json.error
      ? json.error
      : { code: 'UNKNOWN', message: res.statusText || 'Request failed' }
  if (errBody.code === 'UNKNOWN' && res.status >= 500) {
    errBody = {
      code: 'UNKNOWN',
      message:
        `后端错误 HTTP ${res.status}；若刚拉代码请在 backend/ 执行 uv run alembic upgrade head`,
    }
  }
  throw new ApiError(res.status, errBody)
}

function networkErrorMessage(cause: unknown): string {
  const msg = cause instanceof Error ? cause.message : String(cause)
  const lower = msg.toLowerCase()
  if (lower.includes('failed to fetch') || lower.includes('networkerror') || lower.includes('load failed')) {
    return (
      '无法连接后端：请确认 API 已在 http://127.0.0.1:8000 启动；' +
      '若刚拉代码，请在 backend/ 执行 uv run alembic upgrade head'
    )
  }
  return msg || '网络请求失败'
}

async function request<T>(path: string, options: RequestOptions, parse: (res: Response) => Promise<T>): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${env.apiBaseUrl}${path}`, {
      method: options.method ?? 'GET',
      headers: buildHeaders(options),
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    })
  } catch (cause) {
    throw new TypeError(networkErrorMessage(cause))
  }

  if (res.status === 401 && options.token) {
    const next = await maybeRefresh(options)
    if (next) {
      return request(path, { ...options, token: next, _retried: true }, parse)
    }
  }

  if (!res.ok) await parseError(res)
  return parse(res)
}

// single-flight：N 个请求同时收到 401 时，只触发一次 refresh，避免 refresh token
// 轮换语义下并发刷新互相把对方登出。JS 单线程保证 maybeRefresh 同步前缀（设值）先于
// 其他请求的同步前缀（读值）执行，故不会重复创建刷新 promise。
// 单飞对象绑定发起刷新所用的 refresh token：换号后旧单飞不再被新账号的请求复用，
// 避免拿到属于上一个账号的刷新结果。
let refreshInFlight: { token: string; promise: Promise<string | null> } | null = null

function performRefresh(): Promise<string | null> {
  const store = useAuthStore.getState()
  const refresh = store.refresh_token
  const user = store.user
  if (!refresh || !user) return Promise.resolve(null)
  return (async () => {
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
      // 仅当 store 里的 refresh_token 仍是发起本次刷新的那个时才清会话；
      // 否则说明期间已发生登出/换号，当前会话属于另一个账号，不能误清。
      if (store.refresh_token === refresh) {
        store.clearSession()
      }
      return null
    }
  })()
}

async function maybeRefresh(options: RequestOptions): Promise<string | null> {
  if (options._retried) return null
  const currentRefresh = useAuthStore.getState().refresh_token
  // 仅复用「同一 refresh token 发起」的在飞刷新；换号后 currentRefresh 变化，旧单飞作废。
  if (refreshInFlight && currentRefresh && refreshInFlight.token === currentRefresh) {
    return refreshInFlight.promise
  }
  const token = currentRefresh ?? ''
  const promise = performRefresh()
  refreshInFlight = { token, promise }
  try {
    return await promise
  } finally {
    refreshInFlight = null
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request(path, options, async (res) => {
    const json = (await res.json().catch(() => null)) as { data: T } | null
    if (!json || !('data' in json)) {
      throw new ApiError(500, { code: 'UNKNOWN', message: 'Invalid response shape' })
    }
    return json.data
  })
}

export async function apiRequestNoContent(path: string, options: RequestOptions = {}): Promise<void> {
  await request(path, options, async (res) => {
    if (res.status === 204) return
    const json = (await res.json().catch(() => null)) as { data?: unknown } | null
    if (json && 'data' in json) return
    throw new ApiError(500, { code: 'UNKNOWN', message: 'Invalid response shape' })
  })
}

export async function apiRequestList<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiListSuccess<T>> {
  return request(path, options, async (res) => {
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
  })
}

export type DownloadedFile = {
  blob: Blob
  filename: string | null
}

function filenameFromContentDisposition(value: string | null): string | null {
  if (!value) return null
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      return null
    }
  }
  return value.match(/filename="?([^";]+)"?/i)?.[1] ?? null
}

export async function apiRequestFile(
  path: string,
  options: RequestOptions = {},
): Promise<DownloadedFile> {
  return request(path, options, async (res) => ({
    blob: await res.blob(),
    filename: filenameFromContentDisposition(res.headers.get('Content-Disposition')),
  }))
}

/** 拉取非 JSON 纯文本响应体（如产物源码），复用 request 的统一 401 refresh。 */
export async function apiRequestText(
  path: string,
  options: RequestOptions = {},
): Promise<string> {
  return request(path, options, (res) => res.text())
}
