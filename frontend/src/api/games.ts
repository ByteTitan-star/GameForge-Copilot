import { apiRequest, apiRequestFile, apiRequestList, apiRequestText } from './client'
import type {
  ArtifactFile,
  CreateGameResponse,
  GameBatchDeleteResponse,
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
import type { ForgeMessage } from './types'

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

  removeBatch(gameIds: string[], accessToken: string) {
    return apiRequest<GameBatchDeleteResponse>(`/games/batch-delete`, {
      method: 'POST',
      token: accessToken,
      body: { game_ids: gameIds },
    })
  },

  /** owner 自助下架已发布游戏（published → taken_down） */
  unpublish(gameId: string, accessToken: string) {
    return apiRequest<CreateGameResponse>(`/games/${gameId}/unpublish`, {
      method: 'POST',
      token: accessToken,
    })
  },

  /** owner 撤回待审核的发布申请（submitted/reviewing → draft） */
  withdrawPublish(gameId: string, accessToken: string) {
    return apiRequest<PublishSubmitResponse>(`/games/${gameId}/publish/withdraw`, {
      method: 'POST',
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
    idempotencyKey?: string,
  ) {
    return apiRequest<RunSummary>(`/games/${gameId}/runs`, {
      method: 'POST',
      token: accessToken,
      body: { requirement, llm_config_id },
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
    })
  },

  listRuns(gameId: string, accessToken: string) {
    return apiRequestList<RunListItem>(`/games/${gameId}/runs`, { token: accessToken })
  },

  listMessages(gameId: string, accessToken: string, limit = 50, before?: string) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (before) params.set('before', before)
    return apiRequest<ForgeMessage[]>(`/games/${gameId}/messages?${params}`, {
      token: accessToken,
    })
  },

  listVersions(gameId: string, accessToken: string) {
    return apiRequestList<GameVersion>(`/games/${gameId}/versions`, { token: accessToken })
  },

  downloadVersion(gameId: string, version: number, accessToken: string) {
    return apiRequestFile(`/games/${gameId}/versions/${version}/download`, {
      token: accessToken,
      headers: { Accept: 'text/html' },
    })
  },

  /** 列出某版本产物下的全部文件（代码预览文件树，owner only）。 */
  listVersionFiles(gameId: string, version: number, accessToken: string) {
    return apiRequestList<ArtifactFile>(
      `/games/${gameId}/versions/${version}/files`,
      { token: accessToken },
    )
  },

  /** 读取某版本产物下单个文件的源码文本（owner only）。

   * path 按段 encodeURIComponent、保留斜杠，避免 `assets/js/app.js` 的 / 被编码成 %2F 导致路由失配。
   */
  fetchVersionFile(
    gameId: string,
    version: number,
    path: string,
    accessToken: string,
  ) {
    const encoded = path.split('/').map(encodeURIComponent).join('/')
    return apiRequestText(
      `/games/${gameId}/versions/${version}/files/${encoded}`,
      { token: accessToken, headers: { Accept: 'text/plain' } },
    )
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

  /** B-A6：回滚 current_version 指针（不删文件） */
  activateVersion(gameId: string, version: number, accessToken: string) {
    return apiRequest<CreateGameResponse>(
      `/games/${gameId}/versions/${version}/activate`,
      {
        method: 'POST',
        token: accessToken,
        body: {},
      },
    )
  },

  /** B-A5：从失败检查点重试 */
  retryRun(runId: string, accessToken: string) {
    return apiRequest<RunControlResponse>(`/runs/${runId}/retry`, {
      method: 'POST',
      token: accessToken,
      body: {},
    })
  },

  /** 签发 draft 多文件 preview token（owner only，§19.2） */
  createPreviewToken(gameId: string, version: number, accessToken: string) {
    return apiRequest<PreviewTokenResponse>(
      `/games/${gameId}/versions/${version}/preview-token`,
      { method: 'POST', token: accessToken },
    )
  },

  /** 跨游戏进行中的 run（刷新/跳转后找回） */
  listActiveRuns(accessToken: string) {
    return apiRequestList<ActiveRunItem>('/me/runs/active', { token: accessToken })
  },
}

export type ActiveRunItem = {
  run_id: string
  game_id: string
  game_title: string
  status: string
  phase: string
  entry_phase: string
  started_at: string
  ws_url: string
}

export type PreviewTokenResponse = {
  preview_url: string
  expires_in_s: number
}
