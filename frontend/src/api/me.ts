import { apiRequest } from './client'
import type { LLMProvider } from './enums'
import type {
  LlmConfig,
  LlmConfigCreateRequest,
  LlmConfigDeleteResponse,
  LlmConfigPatchRequest,
  LlmConfigTestResponse,
  NotificationItem,
  NotificationReadResponse,
  UsageSummary,
} from './types'

export type LlmConfigTestRequest = {
  provider: LLMProvider | string
  model: string
  apikey: string
  base_url?: string | null
}

export type LlmConfigDryTestResponse = {
  tested_ok: boolean
  error?: string | null
}

export const meApi = {
  listLlmConfigs(accessToken: string) {
    return apiRequest<LlmConfig[]>('/me/llm-configs', { token: accessToken })
  },

  /** 按 provider 拉可选模型；失败时后端回退白名单 */
  listModels(accessToken: string, provider: LLMProvider | string = 'anthropic') {
    const q = `?provider=${encodeURIComponent(provider)}`
    return apiRequest<string[]>(`/me/llm-configs/models${q}`, { token: accessToken })
  },

  createLlmConfig(body: LlmConfigCreateRequest, accessToken: string) {
    return apiRequest<LlmConfig>('/me/llm-configs', {
      method: 'POST',
      token: accessToken,
      body,
    })
  },

  patchLlmConfig(configId: string, body: LlmConfigPatchRequest, accessToken: string) {
    return apiRequest<LlmConfig>(`/me/llm-configs/${configId}`, {
      method: 'PATCH',
      token: accessToken,
      body,
    })
  },

  deleteLlmConfig(configId: string, accessToken: string) {
    return apiRequest<LlmConfigDeleteResponse>(`/me/llm-configs/${configId}`, {
      method: 'DELETE',
      token: accessToken,
    })
  },

  testLlmConfig(configId: string, accessToken: string) {
    return apiRequest<LlmConfigTestResponse>(`/me/llm-configs/${configId}/test`, {
      method: 'POST',
      token: accessToken,
    })
  },

  testLlmConfigDraft(body: LlmConfigTestRequest, accessToken: string) {
    return apiRequest<LlmConfigDryTestResponse>('/me/llm-configs/test', {
      method: 'POST',
      token: accessToken,
      body,
    })
  },

  usage(accessToken: string) {
    return apiRequest<UsageSummary>('/me/usage', { token: accessToken })
  },

  listNotifications(accessToken: string, unreadOnly = false) {
    const q = unreadOnly ? '?unread_only=true' : ''
    return apiRequest<NotificationItem[]>(`/me/notifications${q}`, { token: accessToken })
  },

  markNotificationRead(notificationId: string, accessToken: string) {
    return apiRequest<NotificationReadResponse>(`/me/notifications/${notificationId}/read`, {
      method: 'POST',
      token: accessToken,
      body: {},
    })
  },
}
