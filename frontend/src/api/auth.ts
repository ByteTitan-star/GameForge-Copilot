import { apiRequest, apiRequestNoContent } from './client'
import type {
  LoginResponse,
  PasswordChangeResponse,
  PasswordResetConfirmResponse,
  PasswordResetResponse,
  RefreshResponse,
  RegisterResponse,
  VerifyEmailResponse,
} from './types'

export const authApi = {
  login(email: string, password: string) {
    return apiRequest<LoginResponse>('/auth/login', {
      method: 'POST',
      body: { email, password },
    })
  },

  register(email: string, password: string) {
    return apiRequest<RegisterResponse>('/auth/register', {
      method: 'POST',
      body: { email, password },
    })
  },

  refresh(refresh_token: string) {
    return apiRequest<RefreshResponse>('/auth/refresh', {
      method: 'POST',
      body: { refresh_token },
    })
  },

  /** OpenAPI：204 无体；M0 桩无 requestBody，body 可选兼容 docs/10 */
  logout(refresh_token?: string) {
    return apiRequestNoContent('/auth/logout', {
      method: 'POST',
      body: refresh_token ? { refresh_token } : undefined,
    })
  },

  verifyEmail(token: string) {
    return apiRequest<VerifyEmailResponse>('/auth/verify-email', {
      method: 'POST',
      body: { token },
    })
  },

  requestPasswordReset(email: string) {
    return apiRequest<PasswordResetResponse>('/auth/password/reset', {
      method: 'POST',
      body: { email },
    })
  },

  confirmPasswordReset(token: string, new_password: string) {
    return apiRequest<PasswordResetConfirmResponse>('/auth/password/reset/confirm', {
      method: 'POST',
      body: { token, new_password },
    })
  },

  /** 登录态改密（Bearer） */
  changePassword(old_password: string, new_password: string, accessToken: string) {
    return apiRequest<PasswordChangeResponse>('/auth/password/change', {
      method: 'POST',
      body: { old_password, new_password },
      token: accessToken,
    })
  },
}
