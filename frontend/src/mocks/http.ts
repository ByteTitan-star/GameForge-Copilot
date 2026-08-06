import { HttpResponse } from 'msw'
import { ErrorCode } from '@/api/enums'
import type { MockAccount } from './db'
import { mockDb } from './db'

export function ok<T>(data: T, init?: number | ResponseInit) {
  const status = typeof init === 'number' ? init : (init?.status ?? 200)
  const rest = typeof init === 'number' ? undefined : init
  return HttpResponse.json({ data }, { ...rest, status })
}

export function listOk<T>(data: T[], total = data.length, page = 1, size = 20) {
  return HttpResponse.json({ data, total, page, size })
}

export function fail(status: number, code: string, message: string, detail?: Record<string, unknown>) {
  return HttpResponse.json({ error: { code, message, detail } }, { status })
}

export function getBearer(req: Request): string | null {
  const h = req.headers.get('Authorization')
  if (!h?.startsWith('Bearer ')) return null
  return h.slice('Bearer '.length)
}

export function userFromAccess(token: string | null): MockAccount | null {
  if (!token) return null
  // mock-access.{userId}.{nonce}
  if (token.startsWith('mock-access.')) {
    const userId = token.slice('mock-access.'.length).split('.').slice(0, -1).join('.')
    return mockDb.users.find((u) => u.user_id === userId) ?? null
  }
  // 兼容旧格式：access:{token} -> userId
  const mapped = mockDb.refreshTokens.get(`access:${token}`)
  if (mapped) return mockDb.users.find((u) => u.user_id === mapped) ?? null
  return null
}

export function requireUser(req: Request) {
  const token = getBearer(req)
  const user = userFromAccess(token)
  if (!user) {
    return { user: null as null, error: fail(401, ErrorCode.UNAUTHORIZED, '未登录或 token 失效') }
  }
  return { user, error: null as null }
}

export async function readJson<T>(req: Request): Promise<T> {
  return (await req.json()) as T
}
