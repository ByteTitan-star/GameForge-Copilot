import { env } from '@/lib/env'
import { ApiError } from './errors'
import type { ApiErrorBody, ApiListSuccess } from './types.gen'

type RequestOptions = {
  method?: string
  body?: unknown
  token?: string | null
  signal?: AbortSignal
}

async function parseResponse<T>(res: Response): Promise<T> {
  const json = (await res.json().catch(() => null)) as
    | { data: T }
    | ApiErrorBody
    | ApiListSuccess<T>
    | null

  if (!res.ok) {
    const errBody =
      json && 'error' in json
        ? json.error
        : { code: 'UNKNOWN', message: res.statusText || 'Request failed' }
    throw new ApiError(res.status, errBody)
  }

  if (!json || !('data' in json)) {
    throw new ApiError(500, { code: 'UNKNOWN', message: 'Invalid response shape' })
  }

  return json.data as T
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.token) headers.Authorization = `Bearer ${options.token}`

  const res = await fetch(`${env.apiBaseUrl}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })

  return parseResponse<T>(res)
}

export async function apiRequestList<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiListSuccess<T>> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.token) headers.Authorization = `Bearer ${options.token}`

  const res = await fetch(`${env.apiBaseUrl}${path}`, {
    method: options.method ?? 'GET',
    headers,
    signal: options.signal,
  })

  const json = (await res.json().catch(() => null)) as
    | (ApiListSuccess<T> & Partial<ApiErrorBody>)
    | ApiErrorBody
    | null
  if (!res.ok) {
    const errBody =
      json && 'error' in json && json.error
        ? json.error
        : { code: 'UNKNOWN', message: res.statusText || 'Request failed' }
    throw new ApiError(res.status, errBody)
  }
  if (!json || !('data' in json) || !Array.isArray(json.data)) {
    throw new ApiError(500, { code: 'UNKNOWN', message: 'Invalid list response shape' })
  }
  const data = json.data as T[]
  return {
    data,
    total: 'total' in json && json.total != null ? Number(json.total) : data.length,
    page: 'page' in json && json.page != null ? Number(json.page) : 1,
    size: 'size' in json && json.size != null ? Number(json.size) : data.length,
  }
}
