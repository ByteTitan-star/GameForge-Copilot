#!/usr/bin/env node
/**
 * API 冒烟 — 联调自检。
 * 用法：API=http://127.0.0.1:8000/api/v1 node scripts/real-smoke.mjs
 *
 * 邮箱验证：development 下 register 会把验证码写入 Redis；
 * 脚本通过 GET /dev/verification-code 读取（需 ENV=development）。
 * 也可手动：SMOKE_VERIFY_CODE=123456
 */
const API = (process.env.API ?? 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '')
const BASE = API.replace(/\/api\/v1$/, '')

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

async function req(path, { method = 'GET', token, body, allowError = false } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const json = await res.json().catch(() => null)
  if (!res.ok && !allowError) {
    const msg = json?.error?.message ?? json?.detail ?? res.statusText
    throw new Error(`${res.status} ${msg}`)
  }
  if (json && 'data' in json) return json.data
  return json
}

async function sleep(ms) {
  await new Promise((r) => setTimeout(r, ms))
}

async function resolveVerificationCode() {
  if (process.env.SMOKE_VERIFY_CODE) {
    return process.env.SMOKE_VERIFY_CODE
  }
  try {
    await req('/auth/resend-verification', {
      method: 'POST',
      body: { email },
      allowError: true,
    })
  } catch {
    /* ignore */
  }
  for (let attempt = 0; attempt < 12; attempt += 1) {
    try {
      const res = await fetch(
        `${API}/dev/verification-code?email=${encodeURIComponent(email)}`,
        { headers: { Accept: 'application/json' } },
      )
      const json = await res.json().catch(() => null)
      if (res.ok && json?.data?.code) return String(json.data.code)
    } catch {
      /* retry */
    }
    await sleep(300)
  }
  throw new Error(
    '无法获取验证码：重启 API（含 dev 路由）、确认 ENV=development + Redis，或设置 SMOKE_VERIFY_CODE',
  )
}

async function verifyEmailAndRelogin() {
  const code = await resolveVerificationCode()
  await req('/auth/verify-email', {
    method: 'POST',
    body: { email, code },
  })
  ok('POST /auth/verify-email')
  const login = await req('/auth/login', {
    method: 'POST',
    body: { email, password: `${password}!` },
  })
  return login.access_token
}

async function main() {
  console.log(`Real smoke → ${API}\n`)

  try {
    await fetch(`${BASE}/healthz`)
    ok('GET /healthz')
  } catch (e) {
    fail('GET /healthz', e)
    console.error('\n后端未启动？见 README「联调启动」')
    process.exit(1)
  }

  try {
    const official = await req('/official-games', { allowError: true })
    if (Array.isArray(official) && official.length >= 1) {
      ok(`GET /official-games (${official.length})`)
    } else {
      console.warn('⚠ GET /official-games — 跳过（404 或未 seed，见 scripts/seed_official_games.py）')
    }
  } catch (e) {
    console.warn('⚠ GET /official-games — 跳过:', e instanceof Error ? e.message : e)
  }

  try {
    const playRes = await fetch(`${BASE}/play/official-neon-snake`)
    if (!playRes.ok) throw new Error(`${playRes.status} ${playRes.statusText}`)
    ok('GET /play/official-neon-snake')
  } catch (e) {
    fail('GET /play/official-neon-snake', e)
  }

  let access
  let refresh

  try {
    await req('/auth/register', {
      method: 'POST',
      body: { email, password },
    })
    ok('POST /auth/register')
  } catch (e) {
    fail('POST /auth/register', e)
  }

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
      access = await verifyEmailAndRelogin()
    } catch (e) {
      fail('email verification', e)
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
      const templates = await req('/templates')
      if (!Array.isArray(templates)) throw new Error('expected array')
      ok('GET /templates')
    } catch (e) {
      fail('GET /templates', e)
    }

    try {
      const game = await req('/games', {
        method: 'POST',
        token: access,
        body: {
          title: `smoke-${stamp}`,
          requirement: 'smoke test game requirement',
        },
      })
      await req(`/games/${game.game_id}`, { token: access })
      await req('/games', { token: access })
      ok('POST/GET /games')
    } catch (e) {
      fail('games CRUD', e)
    }

    try {
      const forked = await req('/games/fork/official-neon-snake', {
        method: 'POST',
        token: access,
        allowError: true,
      })
      if (forked?.game_id) {
        ok('POST /games/fork/official-neon-snake')
      } else {
        console.warn('⚠ POST /games/fork/{slug} — 跳过（404 或未 seed）')
      }
    } catch (e) {
      console.warn('⚠ POST /games/fork/{slug} — 跳过:', e instanceof Error ? e.message : e)
    }
  }

  console.log(`\n${passed} passed, ${failed} failed`)
  process.exit(failed > 0 ? 1 : 0)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
