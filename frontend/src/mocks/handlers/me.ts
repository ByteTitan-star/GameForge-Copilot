import { http } from 'msw'
import { ErrorCode, LLMProvider } from '@/api/enums'
import { env } from '@/lib/env'
import { delay, maskKey, mockDb, uid } from '../db'
import { fail, ok, readJson, requireUser } from '../http'

const base = env.apiBaseUrl

function publicConfig(row: (typeof mockDb.llmConfigs)[number]) {
  return {
    config_id: row.config_id,
    provider: row.provider,
    model: row.model,
    apikey_masked: row.apikey_masked,
    is_default: row.is_default,
    tested_ok: row.tested_ok,
  }
}

export const meHandlers = [
  http.get(`${base}/me/llm-configs`, async ({ request }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const data = mockDb.llmConfigs.filter((c) => c.owner_id === user.user_id).map(publicConfig)
    return ok(data)
  }),

  http.post(`${base}/me/llm-configs`, async ({ request }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const body = await readJson<{
      provider: string
      model: string
      apikey: string
      is_default: boolean
    }>(request)
    if (!body.apikey || body.apikey.length < 8) {
      return fail(400, ErrorCode.LLM_CONFIG_INVALID, '连通测试失败：apikey 无效')
    }
    const providers = Object.values(LLMProvider) as string[]
    if (!providers.includes(body.provider)) {
      return fail(400, ErrorCode.VALIDATION_ERROR, 'provider 无效')
    }
    if (body.is_default) {
      mockDb.llmConfigs
        .filter((c) => c.owner_id === user.user_id)
        .forEach((c) => {
          c.is_default = false
        })
    }
    const row = {
      config_id: uid('llm'),
      provider: body.provider as (typeof LLMProvider)[keyof typeof LLMProvider],
      model: body.model,
      apikey: body.apikey,
      apikey_masked: maskKey(body.apikey),
      is_default: Boolean(body.is_default),
      tested_ok: true,
      owner_id: user.user_id,
    }
    mockDb.llmConfigs.push(row)
    return ok(publicConfig(row))
  }),

  http.patch(`${base}/me/llm-configs/:configId`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const row = mockDb.llmConfigs.find(
      (c) => c.config_id === params.configId && c.owner_id === user.user_id,
    )
    if (!row) return fail(404, ErrorCode.VALIDATION_ERROR, '配置不存在')
    const body = await readJson<{ model?: string; is_default?: boolean }>(request)
    if (body.model) row.model = body.model
    if (body.is_default) {
      mockDb.llmConfigs
        .filter((c) => c.owner_id === user.user_id)
        .forEach((c) => {
          c.is_default = c.config_id === row.config_id
        })
    }
    return ok(publicConfig(row))
  }),

  http.delete(`${base}/me/llm-configs/:configId`, async ({ request, params }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const idx = mockDb.llmConfigs.findIndex(
      (c) => c.config_id === params.configId && c.owner_id === user.user_id,
    )
    if (idx < 0) return fail(404, ErrorCode.VALIDATION_ERROR, '配置不存在')
    if (mockDb.llmConfigs[idx].is_default) {
      return fail(409, ErrorCode.INVALID_STATE, '删除默认配置需先指定新默认')
    }
    const config_id = mockDb.llmConfigs[idx].config_id
    mockDb.llmConfigs.splice(idx, 1)
    return ok({ config_id, deleted: true })
  }),

  http.post(`${base}/me/llm-configs/:configId/test`, async ({ request, params }) => {
    await delay(400)
    const { user, error } = requireUser(request)
    if (error) return error
    const row = mockDb.llmConfigs.find(
      (c) => c.config_id === params.configId && c.owner_id === user.user_id,
    )
    if (!row) return fail(404, ErrorCode.VALIDATION_ERROR, '配置不存在')
    const tested_ok = row.apikey.length >= 8
    row.tested_ok = tested_ok
    return ok({
      config_id: row.config_id,
      tested_ok,
      error: tested_ok ? null : '连通失败',
    })
  }),

  http.get(`${base}/me/usage`, async ({ request }) => {
    await delay()
    const { user, error } = requireUser(request)
    if (error) return error
    const u = mockDb.usageByUser.get(user.user_id) ?? {
      today: { input_tokens: 0, output_tokens: 0, calls: 0 },
      month: { input_tokens: 0, output_tokens: 0, calls: 0 },
      total: { input_tokens: 0, output_tokens: 0, calls: 0 },
      daily_token_limit: 500000,
    }
    const daily_used = u.today.input_tokens + u.today.output_tokens
    return ok({
      today: u.today,
      month: u.month,
      total: u.total,
      quota: {
        daily_token_limit: u.daily_token_limit,
        daily_used,
        remaining: Math.max(0, u.daily_token_limit - daily_used),
      },
    })
  }),
]
