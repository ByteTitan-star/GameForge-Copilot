/**
 * 过渡类型（M0）：据 docs/10 §4–5 手写，等价于未来 openapi.json 生成结果的应用层形状。
 *
 * 后端真实 openapi.json 就绪后执行并覆盖本文件：
 *   pnpm exec openapi-typescript ../contracts/openapi.json -o src/api/types.gen.ts
 *
 * 字段保持 snake_case，不做 camel 转换。
 */

import type {
  GameStatus,
  LLMProvider,
  PublishStatus,
  Role,
  RunPhase,
  RunStatus,
  WSEventType,
} from './enums'

export type ApiErrorBody = {
  error: {
    code: string
    message: string
    detail?: Record<string, unknown>
  }
}

export type ApiSuccess<T> = { data: T }

export type ApiListSuccess<T> = {
  data: T[]
  total: number
  page: number
  size: number
}

export type User = {
  user_id: string
  email: string
  role: Role
  email_verified: boolean
}

export type RegisterRequest = { email: string; password: string }
export type RegisterResponse = {
  user_id: string
  email: string
  email_verified: boolean
}

export type LoginRequest = { email: string; password: string }
export type LoginResponse = {
  access_token: string
  refresh_token: string
  expires_in: number
  user: User
}

export type RefreshRequest = { refresh_token: string }
export type RefreshResponse = {
  access_token: string
  refresh_token: string
  expires_in: number
}

export type VerifyEmailRequest = { token: string }
export type VerifyEmailResponse = { user_id: string; email_verified: boolean }

export type PasswordResetRequest = { email: string }
export type PasswordResetResponse = { sent: boolean }

export type PasswordResetConfirmRequest = { token: string; new_password: string }
export type PasswordResetConfirmResponse = { user_id: string; reset: boolean }

export type LogoutRequest = { refresh_token: string }
export type LogoutResponse = { ok?: boolean }

export type LlmConfigCreateRequest = {
  provider: LLMProvider
  model: string
  apikey: string
  is_default: boolean
}

export type LlmConfig = {
  config_id: string
  provider: LLMProvider
  model: string
  apikey_masked: string
  is_default: boolean
  tested_ok?: boolean
}

export type LlmConfigPatchRequest = {
  model?: string
  is_default?: boolean
}

export type LlmConfigTestResponse = {
  config_id: string
  tested_ok: boolean
  error: string | null
}

export type LlmConfigDeleteResponse = {
  config_id: string
  deleted: boolean
}

export type CreateGameRequest = { title: string; requirement: string }
export type CreateGameResponse = {
  game_id: string
  owner_id: string
  status: GameStatus
  current_version: number
  created_at: string
}

export type GameSummary = {
  game_id: string
  title: string
  status: GameStatus
  current_version: number
  slug: string | null
  updated_at: string
}

export type GameVersion = {
  version: number
  artifact_path: string
  created_at: string
}

export type GameDetail = {
  game_id: string
  owner_id: string
  title: string
  status: GameStatus
  current_version: number
  slug: string | null
  versions: GameVersion[]
  created_at: string
  updated_at: string
}

export type StartRunRequest = {
  requirement: string
  llm_config_id: string | null
}

export type RunSummary = {
  run_id: string
  game_id: string
  status: RunStatus
  phase: RunPhase
  ws_url: string
}

export type RunListItem = {
  run_id: string
  status: RunStatus
  phase: RunPhase
  started_at: string
  ended_at: string | null
}

export type RunDetail = {
  run_id: string
  game_id: string
  status: RunStatus
  phase: RunPhase
  ws_url: string
  current_hitl: { node: string } | null
}

export type HitlResolveRequest = {
  node: string
  decision: 'approve' | 'modify'
  modify_text?: string
}

export type HitlResolveResponse = {
  run_id: string
  status: RunStatus
  phase: RunPhase
}

export type PublishSubmitRequest = { version: number; note: string }
export type PublishSubmitResponse = {
  publish_request_id: string
  status: PublishStatus
  game_id: string
  version: number
}

export type PublishQueueItem = {
  publish_request_id: string
  game_id: string
  game_title: string
  version: number
  status: PublishStatus
  created_at: string
}

export type UsageBucket = {
  input_tokens: number
  output_tokens: number
  calls: number
}

export type UsageSummary = {
  today: UsageBucket
  month: UsageBucket
  total: UsageBucket
  quota: {
    daily_token_limit: number
    daily_used: number
    remaining: number
  }
}

export type AdminUsage = {
  system: {
    today: UsageBucket
    month: UsageBucket
    total: UsageBucket
  }
  top_users: Array<{
    user_id: string
    email: string
    month_input_tokens: number
    month_output_tokens: number
    calls: number
  }>
}

export type WsEnvelope<T = Record<string, unknown>> = {
  type: WSEventType
  run_id: string
  ts: string
  payload: T
}

export type PhaseStartPayload = { phase: RunPhase }
export type LlmCallPayload = {
  phase: RunPhase
  model: string
  provider: string
  input_tokens: number
  output_tokens: number
}
export type ToolCallPayload = {
  phase: RunPhase
  tool: string
  status: 'ok' | 'error'
  summary: string
  args?: Record<string, unknown>
}
export type BuildDonePayload = {
  version: number
  artifact_path: string
  preview_url: string
}
export type QaReportPayload = {
  passed: boolean
  issues: string[]
  log_excerpt: string
}
export type HitlWaitPayload = {
  node: string
  design_doc: {
    title: string
    gameplay: string
    controls: string
    levels: string[]
  }
  action_url: string
}
export type UsageEventPayload = {
  today_used: number
  daily_limit: number
  remaining: number
}
export type DonePayload = {
  run_id: string
  game_id: string
  version: number
  preview_url: string
}
export type ErrorPayload = {
  code: string
  message: string
  fatal: boolean
}
