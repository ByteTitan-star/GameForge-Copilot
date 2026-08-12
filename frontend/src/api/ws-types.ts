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

export type HitlWaitPayload = {
  node: string
  design_doc: DesignDocPayload | string
  action_url: string
  error?: string
  errors?: string[]
  issues?: string[]
  retries?: number
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
