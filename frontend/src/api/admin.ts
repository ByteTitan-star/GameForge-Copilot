import { apiRequest, apiRequestList } from './client'
import type {
  AdminSettings,
  AdminUsage,
  AdminUser,
  AdminUserPatch,
  AdminGameItem,
  AuditLogItem,
  PublishApproveResponse,
  PublishQueueItem,
  PublishRejectResponse,
  TakeDownResponse,
} from './types'

export const adminApi = {
  listPublishQueue(accessToken: string, status?: string) {
    const q = status ? `?status=${encodeURIComponent(status)}` : ''
    return apiRequestList<PublishQueueItem>(`/publish/queue${q}`, { token: accessToken })
  },

  approvePublish(publishRequestId: string, accessToken: string) {
    return apiRequest<PublishApproveResponse>(`/publish/${publishRequestId}/approve`, {
      method: 'POST',
      token: accessToken,
      body: {},
    })
  },

  rejectPublish(publishRequestId: string, reason: string, accessToken: string) {
    return apiRequest<PublishRejectResponse>(`/publish/${publishRequestId}/reject`, {
      method: 'POST',
      token: accessToken,
      body: { reason },
    })
  },

  takeDown(gameId: string, reason: string, accessToken: string) {
    return apiRequest<TakeDownResponse>(`/games/${gameId}/take-down`, {
      method: 'POST',
      token: accessToken,
      body: { reason },
    })
  },

  listUsers(accessToken: string, page = 1, size = 20) {
    return apiRequestList<AdminUser>(`/admin/users?page=${page}&size=${size}`, {
      token: accessToken,
    })
  },

  patchUser(userId: string, body: AdminUserPatch, accessToken: string) {
    return apiRequest<AdminUser>(`/admin/users/${userId}`, {
      method: 'PATCH',
      token: accessToken,
      body,
    })
  },

  deleteUser(userId: string, accessToken: string) {
    return apiRequest<void>(`/admin/users/${userId}`, {
      method: 'DELETE',
      token: accessToken,
    })
  },

  usage(accessToken: string) {
    return apiRequest<AdminUsage>('/admin/usage', { token: accessToken })
  },

  getSettings(accessToken: string) {
    return apiRequest<AdminSettings>('/admin/settings', { token: accessToken })
  },

  updateSettings(body: AdminSettings, accessToken: string) {
    return apiRequest<AdminSettings>('/admin/settings', {
      method: 'PUT',
      token: accessToken,
      body,
    })
  },

  listGames(accessToken: string, status?: string, page = 1, size = 20) {
    const params = new URLSearchParams({ page: String(page), size: String(size) })
    if (status) params.set('status', status)
    return apiRequestList<AdminGameItem>(`/admin/games?${params.toString()}`, {
      token: accessToken,
    })
  },

  listAuditLogs(accessToken: string, page = 1, size = 20) {
    return apiRequestList<AuditLogItem>(`/admin/audit-logs?page=${page}&size=${size}`, {
      token: accessToken,
    })
  },

  setFeatured(gameId: string, featured: boolean, accessToken: string) {
    return apiRequest<{ featured: boolean }>(`/admin/games/${gameId}/featured`, {
      method: 'PATCH',
      token: accessToken,
      body: { featured },
    })
  },
}
