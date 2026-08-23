/** 与 docs/10-contract-and-parallel-dev.md §2 字面量必须一致 */

export const Role = {
  user: 'user',
  admin: 'admin',
} as const
export type Role = (typeof Role)[keyof typeof Role]

export const GameStatus = {
  draft: 'draft',
  submitted: 'submitted',
  reviewing: 'reviewing',
  published: 'published',
  rejected: 'rejected',
  taken_down: 'taken_down',
} as const
export type GameStatus = (typeof GameStatus)[keyof typeof GameStatus]

export const RunStatus = {
  running: 'running',
  paused: 'paused',
  done: 'done',
  failed: 'failed',
  cancelled: 'cancelled',
} as const
export type RunStatus = (typeof RunStatus)[keyof typeof RunStatus]

export const RunPhase = {
  plan: 'plan',
  art: 'art',
  code: 'code',
  qa: 'qa',
  done: 'done',
} as const
export type RunPhase = (typeof RunPhase)[keyof typeof RunPhase]

export const PublishStatus = {
  submitted: 'submitted',
  reviewing: 'reviewing',
  approved: 'approved',
  rejected: 'rejected',
  withdrawn: 'withdrawn',
} as const
export type PublishStatus = (typeof PublishStatus)[keyof typeof PublishStatus]

export const LLMProvider = {
  anthropic: 'anthropic',
  openai: 'openai',
  openai_compat: 'openai_compat',
} as const
export type LLMProvider = (typeof LLMProvider)[keyof typeof LLMProvider]

export const WSEventType = {
  phase_start: 'phase_start',
  llm_call: 'llm_call',
  // LLM 流式微批增量：payload 含 phase + delta（打字机文本，3-5 字一批）
  llm_delta: 'llm_delta',
  tool_call: 'tool_call',
  build_done: 'build_done',
  qa_report: 'qa_report',
  hitl_wait: 'hitl_wait',
  usage: 'usage',
  done: 'done',
  // 内容审核命中（输入注入/输出恶意）：前端断 WS + 弹友好提示
  attacked: 'attacked',
  error: 'error',
} as const
export type WSEventType = (typeof WSEventType)[keyof typeof WSEventType]

export const ErrorCode = {
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  EMAIL_NOT_VERIFIED: 'EMAIL_NOT_VERIFIED',
  RATE_LIMITED: 'RATE_LIMITED',
  QUOTA_EXCEEDED: 'QUOTA_EXCEEDED',
  LLM_CONFIG_INVALID: 'LLM_CONFIG_INVALID',
  GAME_NOT_FOUND: 'GAME_NOT_FOUND',
  INVALID_STATE: 'INVALID_STATE',
  SANDBOX_FAILED: 'SANDBOX_FAILED',
  EMAIL_TAKEN: 'EMAIL_TAKEN',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
} as const
export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode]
