import { apiRequest } from './client'

export type UserProfile = {
  handle: string | null
  display_name: string | null
  profile_public: boolean
  email?: string
}

export type ProfilePatch = {
  handle?: string
  display_name?: string
  profile_public?: boolean
}

export const profileApi = {
  get(accessToken: string) {
    return apiRequest<UserProfile>('/me/profile', { token: accessToken })
  },

  patch(body: ProfilePatch, accessToken: string) {
    return apiRequest<UserProfile>('/me/profile', {
      method: 'PATCH',
      token: accessToken,
      body,
    })
  },
}
