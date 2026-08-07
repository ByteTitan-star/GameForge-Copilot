import { apiRequest, apiRequestList } from './client'
import type {
  CreateGameResponse,
  GameDeleteResponse,
  GameDetail,
  GamePatchRequest,
  GameSummary,
  GameVersion,
  HitlResolveRequest,
  HitlResolveResponse,
  PublishSubmitResponse,
  RunControlResponse,
  RunDetail,
  RunListItem,
  RunSummary,
} from './types'

export const gamesApi = {
  list(accessToken: string, status?: string) {
    const q = status ? `?status=${encodeURIComponent(status)}` : ''
    return apiRequestList<GameSummary>(`/games${q}`, { token: accessToken })
  },

  get(gameId: string, accessToken: string) {
    return apiRequest<GameDetail>(`/games/${gameId}`, { token: accessToken })
  },

  create(title: string, requirement: string, accessToken: string) {
    return apiRequest<CreateGameResponse>('/games', {
      method: 'POST',
      token: accessToken,
      body: { title, requirement },
    })
  },

  remove(gameId: string, accessToken: string) {
    return apiRequest<GameDeleteResponse>(`/games/${gameId}`, {
      method: 'DELETE',
      token: accessToken,
    })
  },

  patch(gameId: string, body: GamePatchRequest, accessToken: string) {
    return apiRequest<CreateGameResponse>(`/games/${gameId}`, {
      method: 'PATCH',
      token: accessToken,
      body,
    })
  },

  startRun(
    gameId: string,
    requirement: string,
    accessToken: string,
    llm_config_id: string | null = null,
  ) {
    return apiRequest<RunSummary>(`/games/${gameId}/runs`, {
      method: 'POST',
      token: accessToken,
      body: { requirement, llm_config_id },
    })
  },

  listRuns(gameId: string, accessToken: string) {
    return apiRequestList<RunListItem>(`/games/${gameId}/runs`, { token: accessToken })
  },

  listVersions(gameId: string, accessToken: string) {
    return apiRequestList<GameVersion>(`/games/${gameId}/versions`, { token: accessToken })
  },

  getRun(runId: string, accessToken: string) {
    return apiRequest<RunDetail>(`/runs/${runId}`, { token: accessToken })
  },

  pauseRun(runId: string, accessToken: string) {
    return apiRequest<RunControlResponse>(`/runs/${runId}/pause`, {
      method: 'POST',
      token: accessToken,
      body: {},
    })
  },

  resumeRun(runId: string, accessToken: string) {
    return apiRequest<RunControlResponse>(`/runs/${runId}/resume`, {
      method: 'POST',
      token: accessToken,
      body: {},
    })
  },

  cancelRun(runId: string, accessToken: string) {
    return apiRequest<RunControlResponse>(`/runs/${runId}/cancel`, {
      method: 'POST',
      token: accessToken,
      body: {},
    })
  },

  resolveHitl(gameId: string, runId: string, body: HitlResolveRequest, accessToken: string) {
    return apiRequest<HitlResolveResponse>(`/games/${gameId}/runs/${runId}/hitl/resolve`, {
      method: 'POST',
      token: accessToken,
      body,
    })
  },

  submitPublish(gameId: string, version: number, note: string, accessToken: string) {
    return apiRequest<PublishSubmitResponse>(`/games/${gameId}/publish/submit`, {
      method: 'POST',
      token: accessToken,
      body: { version, note },
    })
  },
}
