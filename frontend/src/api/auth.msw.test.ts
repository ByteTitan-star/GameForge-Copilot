import { describe, expect, it } from 'vitest'
import { authApi } from './auth'
import { meApi } from './me'
import { ApiError } from './errors'

describe('MSW · 认证与用量', () => {
  it('login 成功返回 snake_case session', async () => {
    const data = await authApi.login('demo@gameforge.dev', 'password123')
    expect(data.access_token).toMatch(/^mock-access\./)
    expect(data.user.email_verified).toBe(true)
    expect(data.user.role).toBe('user')
  })

  it('login 失败抛 ApiError', async () => {
    await expect(authApi.login('fail@test.com', 'x')).rejects.toBeInstanceOf(ApiError)
  })

  it('usage schema 对齐 docs/10', async () => {
    const login = await authApi.login('demo@gameforge.dev', 'password123')
    const usage = await meApi.usage(login.access_token)
    expect(usage.today).toHaveProperty('input_tokens')
    expect(usage.quota).toMatchObject({
      daily_token_limit: expect.any(Number),
      daily_used: expect.any(Number),
      remaining: expect.any(Number),
    })
  })
})
