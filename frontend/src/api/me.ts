import { apiRequest } from './client'
import type {
  LlmConfig,
  LlmConfigCreateRequest,
  LlmConfigDeleteResponse,
  LlmConfigPatchRequest,
  LlmConfigTestResponse,
  UsageSummary,
} from './types.gen'

export const meApi = {
  listLlmConfigs(accessToken: string) {
    return apiRequest<LlmConfig[]>('/me/llm-configs', { token: accessToken })
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

  usage(accessToken: string) {
    return apiRequest<UsageSummary>('/me/usage', { token: accessToken })
  },
}
