import { http } from 'msw'
import { ErrorCode, Role } from '@/api/enums'
import { env } from '@/lib/env'
import { delay, mockDb, uid } from '../db'
import { fail, ok, readJson } from '../http'

const base = env.apiBaseUrl

function toUser(account: (typeof mockDb.users)[number]) {
  return {
    user_id: account.user_id,
    email: account.email,
    role: account.role,
    email_verified: account.email_verified,
  }
}

function issueTokens(userId: string) {
  const access_token = `mock-access-${uid('a')}`
  const refresh_token = `mock-refresh-${uid('r')}`
  mockDb.refreshTokens.set(refresh_token, userId)
  mockDb.refreshTokens.set(`access:${access_token}`, userId)
  return { access_token, refresh_token, expires_in: 900 }
}

export const authHandlers = [
  http.post(`${base}/auth/login`, async ({ request }) => {
    await delay()
    const body = await readJson<{ email: string; password: string }>(request)
    if (body.email === 'fail@test.com') {
      return fail(401, ErrorCode.UNAUTHORIZED, '邮箱或密码错误')
    }
    const account = mockDb.users.find((u) => u.email === body.email)
    if (!account || account.password !== body.password) {
      return fail(401, ErrorCode.UNAUTHORIZED, '邮箱或密码错误')
    }
    return ok({ ...issueTokens(account.user_id), user: toUser(account) })
  }),

  http.post(`${base}/auth/register`, async ({ request }) => {
    await delay()
    const body = await readJson<{ email: string; password: string }>(request)
    if (!body.email?.includes('@') || (body.password?.length ?? 0) < 6) {
      return fail(400, ErrorCode.VALIDATION_ERROR, '邮箱格式无效或密码不足 6 位', {
        email: 'invalid',
        password: 'too_short',
      })
    }
    if (mockDb.users.some((u) => u.email === body.email)) {
      return fail(409, ErrorCode.EMAIL_TAKEN, '该邮箱已注册')
    }
    const user_id = uid('u')
    mockDb.users.push({
      user_id,
      email: body.email,
      password: body.password,
      role: Role.user,
      email_verified: false,
    })
    mockDb.verifyCodes.set(body.email, '123456')
    return ok({ user_id, email: body.email, email_verified: false })
  }),

  http.post(`${base}/auth/refresh`, async ({ request }) => {
    await delay(200)
    const body = await readJson<{ refresh_token: string }>(request)
    const userId = mockDb.refreshTokens.get(body.refresh_token)
    if (!userId) return fail(401, ErrorCode.UNAUTHORIZED, 'refresh token 无效')
    mockDb.refreshTokens.delete(body.refresh_token)
    return ok(issueTokens(userId))
  }),

  http.post(`${base}/auth/logout`, async ({ request }) => {
    await delay(150)
    const body = await readJson<{ refresh_token: string }>(request)
    mockDb.refreshTokens.delete(body.refresh_token)
    return ok({ ok: true })
  }),

  http.post(`${base}/auth/verify-email`, async ({ request }) => {
    await delay()
    const body = await readJson<{ token: string }>(request)
    const byEmail = mockDb.users.find((u) => u.email === body.token)
    const byCode = [...mockDb.verifyCodes.entries()].find(([, code]) => code === body.token)
    const account =
      byEmail ?? (byCode ? mockDb.users.find((u) => u.email === byCode[0]) : undefined)
    if (!account) return fail(400, ErrorCode.VALIDATION_ERROR, '验证码无效或已过期')
    account.email_verified = true
    return ok({ user_id: account.user_id, email_verified: true })
  }),

  http.post(`${base}/auth/password/reset`, async ({ request }) => {
    await delay()
    const body = await readJson<{ email: string }>(request)
    if (mockDb.users.some((u) => u.email === body.email)) {
      mockDb.verifyCodes.set(`reset:${body.email}`, '654321')
    }
    return ok({ sent: true })
  }),

  http.post(`${base}/auth/password/reset/confirm`, async ({ request }) => {
    await delay()
    const body = await readJson<{ token: string; new_password: string }>(request)
    const entry = [...mockDb.verifyCodes.entries()].find(
      ([k, v]) => k.startsWith('reset:') && (v === body.token || k === `reset:${body.token}`),
    )
    if (!entry || body.new_password.length < 6) {
      return fail(400, ErrorCode.VALIDATION_ERROR, '重置令牌无效或密码过短')
    }
    const email = entry[0].replace('reset:', '')
    const account = mockDb.users.find((u) => u.email === email)
    if (!account) return fail(400, ErrorCode.VALIDATION_ERROR, '重置令牌无效')
    account.password = body.new_password
    mockDb.verifyCodes.delete(entry[0])
    return ok({ user_id: account.user_id, reset: true })
  }),
]
