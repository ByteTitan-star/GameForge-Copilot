import { apiRequest } from './client'
import type {
  LoginResponse,
  LogoutResponse,
  PasswordResetConfirmResponse,
  PasswordResetResponse,
  RefreshResponse,
  RegisterResponse,
  VerifyEmailResponse,
} from './types.gen'

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

  logout(refresh_token: string) {
    return apiRequest<LogoutResponse>('/auth/logout', {
      method: 'POST',
      body: { refresh_token },
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
}
