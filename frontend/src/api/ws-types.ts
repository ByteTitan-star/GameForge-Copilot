/**
 * WS 事件契约（docs/10 §5）。不进 OpenAPI，浏览器原生 WS 无 schema。
 */
import type { RunPhase, WSEventType } from './enums'

export type WsEnvelope<T = Record<string, unknown>> = {
  type: WSEventType
  run_id: string
  ts: string
  seq?: number
  payload: T
}

export type PhaseStartPayload = {
  phase: RunPhase
  human_label?: string
  eta_seconds?: number
}
export type LlmCallPayload = {
  phase: RunPhase
  model: string
  provider: string
  input_tokens: number
  output_tokens: number
}
/** LLM 流式微批增量（打字机文本）。后端 run_streamed_llm 攒 3-5 字发一批。 */
export type LlmDeltaPayload = {
  phase: RunPhase
  delta: string
}
/** 内容审核命中：后端护栏拦截后发，前端断 WS + 弹友好提示。 */
export type AttackedPayload = {
  phase: RunPhase
  /** input=输入注入命中，output=生成内容命中 */
  side: 'input' | 'output'
  /** jailbreak|harmful_code|pii|politics */
  category: string
  reason: string
  /** 给用户看的中文提示 */
  message: string
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
export type DesignDocPayload = {
  title: string
  gameplay: string
  controls: string
  levels: string[] | Record<string, unknown>[]
}

export type ArtDirectionOption = {
  id: 'A' | 'B'
  name: string
  summary: string
  recommended: boolean
}

export type ArtOptionsPayload = {
  options: ArtDirectionOption[]
}

export type HitlFailurePayload = {
  failure_class?: string
  summary?: string
  suggested_recovery?: string
  failure_report_id?: string
}

export type HitlWaitPayload = {
  node: string
  design_doc: DesignDocPayload | string
  action_url: string
  error?: string
  errors?: string[]
  issues?: string[]
  retries?: number
  art_options?: ArtOptionsPayload
  allowed_commands?: string[]
  control_revision?: number
  failure?: HitlFailurePayload | null
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
