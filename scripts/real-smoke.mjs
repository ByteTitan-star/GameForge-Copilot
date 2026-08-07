#!/usr/bin/env node
/**
 * Real API smoke — 路径 B 联调自检。
 * 用法：API=http://127.0.0.1:8000/api/v1 node scripts/real-smoke.mjs
 */
const API = (process.env.API ?? 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '')

const stamp = Date.now()
const email = `smoke-${stamp}@example.com`
const password = 'password12345'

let passed = 0
let failed = 0

function ok(label) {
  passed += 1
  console.log(`✓ ${label}`)
}

function fail(label, err) {
  failed += 1
  console.error(`✗ ${label}:`, err instanceof Error ? err.message : err)
}

async function req(path, { method = 'GET', token, body } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const json = await res.json().catch(() => null)
  if (!res.ok) {
    const msg = json?.error?.message ?? json?.detail ?? res.statusText
    throw new Error(`${res.status} ${msg}`)
  }
  if (json && 'data' in json) return json.data
  return json
}

async function main() {
  console.log(`Real smoke → ${API}\n`)

  try {
    await fetch(`${API.replace(/\/api\/v1$/, '')}/healthz`)
    ok('GET /healthz')
  } catch (e) {
    fail('GET /healthz', e)
    console.error('\n后端未启动？见 README 路径 B')
    process.exit(1)
  }

  let access
  let refresh
  let userId

  try {
    const reg = await req('/auth/register', {
      method: 'POST',
      body: { email, password },
    })
    userId = reg.user_id
    ok('POST /auth/register')
  } catch (e) {
    fail('POST /auth/register', e)
  }

  // dev 环境 token 由 worker 打印；冒烟用 verify 需从 DB/日志取 token。
  // 此处跳过 verify，直接测 login（未验证应仍可 login，生成会被拦）
  try {
    const login = await req('/auth/login', {
      method: 'POST',
      body: { email, password },
    })
    access = login.access_token
    refresh = login.refresh_token
    ok('POST /auth/login')
  } catch (e) {
    fail('POST /auth/login', e)
  }

  if (refresh) {
    try {
      const tokens = await req('/auth/refresh', {
        method: 'POST',
        body: { refresh_token: refresh },
      })
      access = tokens.access_token
      ok('POST /auth/refresh')
    } catch (e) {
      fail('POST /auth/refresh', e)
    }
  }

  if (access) {
    try {
      await req('/auth/password/change', {
        method: 'POST',
        token: access,
        body: { old_password: password, new_password: `${password}!` },
      })
      ok('POST /auth/password/change')
      const relogin = await req('/auth/login', {
        method: 'POST',
        body: { email, password: `${password}!` },
      })
      access = relogin.access_token
    } catch (e) {
      fail('POST /auth/password/change', e)
    }

    try {
      const models = await req('/me/llm-configs/models?provider=anthropic', { token: access })
      if (!Array.isArray(models)) throw new Error('expected array')
      ok('GET /me/llm-configs/models')
    } catch (e) {
      fail('GET /me/llm-configs/models', e)
    }

    try {
      await req('/me/usage', { token: access })
      ok('GET /me/usage')
    } catch (e) {
      fail('GET /me/usage', e)
    }

    try {
      const game = await req('/games', {
        method: 'POST',
        token: access,
        body: { title: `smoke-${stamp}` },
      })
      await req(`/games/${game.game_id}`, { token: access })
      await req('/games', { token: access })
      ok('POST/GET /games')
    } catch (e) {
      fail('games CRUD', e)
    }
  }

  console.log(`\n${passed} passed, ${failed} failed`)
  process.exit(failed > 0 ? 1 : 0)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
