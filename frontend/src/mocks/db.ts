import { GameStatus, LLMProvider, Role } from '@/api/enums'
import type { GameSummary, LlmConfig, User } from '@/api/types'

export type MockAccount = User & { password: string }

export type MockGame = GameSummary & {
  owner_id: string
  cover?: string
  created_at: string
}

const now = () => new Date().toISOString()

/** 内存 mock 库；刷新页面会重置（token 仍在 localStorage，需重新登录） */
export const mockDb = {
  users: [
    {
      user_id: 'u-demo',
      email: 'demo@gameforge.dev',
      password: 'password123',
      role: Role.user,
      email_verified: true,
    },
    {
      user_id: 'u-unverified',
      email: 'unverified@gameforge.dev',
      password: 'password123',
      role: Role.user,
      email_verified: false,
    },
    {
      user_id: 'u-admin',
      email: 'admin@gameforge.dev',
      password: 'password123',
      role: Role.admin,
      email_verified: true,
    },
  ] as MockAccount[],

  games: [
    {
      game_id: 'g-snake',
      title: '霓虹贪吃蛇',
      status: GameStatus.draft,
      current_version: 1,
      slug: null,
      updated_at: now(),
      created_at: now(),
      owner_id: 'u-demo',
      cover: 'snake',
    },
    {
      game_id: 'g-runner',
      title: '像素跑酷',
      status: GameStatus.published,
      current_version: 2,
      slug: 'pixel-runner',
      updated_at: now(),
      created_at: now(),
      owner_id: 'u-demo',
      cover: 'runner',
    },
    {
      game_id: 'g-tower',
      title: '塔防雏形',
      status: GameStatus.rejected,
      current_version: 1,
      slug: null,
      updated_at: now(),
      created_at: now(),
      owner_id: 'u-demo',
      cover: 'tower',
    },
  ] as MockGame[],

  llmConfigs: [
    {
      config_id: 'llm-1',
      provider: LLMProvider.anthropic,
      model: 'claude-sonnet-4-20250514',
      apikey_masked: 'sk-***demo***',
      is_default: true,
      tested_ok: true,
      owner_id: 'u-demo',
      apikey: 'sk-demo-key',
    },
  ] as Array<LlmConfig & { owner_id: string; apikey: string }>,

  usageByUser: new Map<
    string,
    {
      today: { input_tokens: number; output_tokens: number; calls: number }
      month: { input_tokens: number; output_tokens: number; calls: number }
      total: { input_tokens: number; output_tokens: number; calls: number }
      daily_token_limit: number
    }
  >([
    [
      'u-demo',
      {
        today: { input_tokens: 10200, output_tokens: 2823, calls: 12 },
        month: { input_tokens: 150000, output_tokens: 36000, calls: 186 },
        total: { input_tokens: 900000, output_tokens: 210000, calls: 1200 },
        daily_token_limit: 500000,
      },
    ],
  ]),

  publishQueue: [] as Array<{
    publish_request_id: string
    game_id: string
    game_title: string
    version: number
    status: 'submitted' | 'reviewing' | 'approved' | 'rejected'
    created_at: string
    owner_id: string
  }>,

  refreshTokens: new Map<string, string>(),
  verifyCodes: new Map<string, string>(),
  runs: new Map<
    string,
    {
      run_id: string
      game_id: string
      owner_id: string
      status: 'running' | 'paused' | 'done' | 'failed'
      phase: 'plan' | 'art' | 'code' | 'qa' | 'done'
      started_at: string
      ended_at: string | null
      current_hitl: { node: string } | null
    }
  >(),
}

export function delay(ms = 280) {
  return new Promise((r) => setTimeout(r, ms))
}

export function uid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

export function maskKey(apikey: string) {
  if (apikey.length <= 8) return '***'
  return `${apikey.slice(0, 3)}-***${apikey.slice(-3)}***`
}
