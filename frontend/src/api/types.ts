/**
 * 应用侧类型别名。真相源：openapi-typescript → types.gen.ts
 * WS 事件不在 OpenAPI 中，见 ws-types.ts / docs/10 §5
 */
import type { components } from './types.gen'

type S = components['schemas']

export type User = S['UserPublic']
export type LoginResponse = S['LoginResp']
export type RegisterResponse = S['RegisterResp']
export type RefreshResponse = S['TokenResp']
export type VerifyEmailResponse = S['VerifyEmailResp']
export type ResendVerificationResponse = S['ResendVerificationResp']
export type PasswordResetResponse = S['PasswordResetResp']
export type PasswordResetConfirmResponse = S['PasswordResetConfirmResp']
export type PasswordChangeResponse = S['PasswordChangeResp']
export type PasswordChangeRequest = S['PasswordChangeReq']

export type LlmConfig = S['LLMConfigResp'] & { tested_ok?: boolean }
export type LlmConfigCreateRequest = S['LLMConfigCreate']
export type LlmConfigPatchRequest = S['LLMConfigPatch']
export type LlmConfigTestResponse = S['LLMConfigTestResp']
export type LlmConfigDeleteResponse = S['LLMConfigDeleteResp']

export type GameSummary = S['GameListItem']
export type GameDetail = S['GameDetailResp']
export type GameVersion = S['VersionItem']
export type CreateGameResponse = S['GameResp']
export type GameDeleteResponse = S['GameDeleteResp']
export type GamePatchRequest = S['GamePatch']

export type RunSummary = S['RunResp']
export type RunDetail = S['RunStatusResp']
export type RunListItem = S['RunListItem']
export type HitlResolveRequest = S['HitlResolveReq']
export type HitlResolveResponse = S['HitlResolveResp']
export type RunControlResponse = S['RunControlResp']

export type PublishSubmitResponse = S['PublishSubmitResp']
export type PublishQueueItem = S['PublishQueueItem']
export type PublishApproveResponse = S['PublishApproveResp']
export type PublishRejectResponse = S['PublishRejectResp']
export type TakeDownResponse = S['TakeDownResp']

export type UsageSummary = S['UsageResp']
export type UsageBucket = S['UsageBucket']
export type AdminUsage = S['AdminUsageResp']
export type AdminUser = S['AdminUserItem']
export type AdminUserPatch = S['AdminUserPatch']
export type AdminSettings = S['AdminSettings']
export type AdminGameItem = S['AdminGameItem']
export type AuditLogItem = S['AuditLogItem']
export type NotificationItem = S['NotificationItem']
export type NotificationReadResponse = S['NotificationReadResp']

/** 统一错误信封（docs/10 §3；OpenAPI 422 另有 HTTPValidationError） */
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

export type {
  HitlWaitPayload,
  WsEnvelope,
} from './ws-types'
