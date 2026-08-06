import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '@/api/auth'
import type { User } from '@/api/types'

type AuthState = {
  user: User | null
  access_token: string | null
  refresh_token: string | null
  hydrated: boolean
  setHydrated: (v: boolean) => void
  setSession: (payload: {
    user: User
    access_token: string
    refresh_token: string
  }) => void
  patchUser: (patch: Partial<User>) => void
  clearSession: () => void
  logout: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      access_token: null,
      refresh_token: null,
      hydrated: false,
      setHydrated: (v) => set({ hydrated: v }),
      setSession: ({ user, access_token, refresh_token }) =>
        set({ user, access_token, refresh_token }),
      patchUser: (patch) => {
        const user = get().user
        if (!user) return
        set({ user: { ...user, ...patch } })
      },
      clearSession: () => set({ user: null, access_token: null, refresh_token: null }),
      logout: async () => {
        const refresh = get().refresh_token
        try {
          if (refresh) await authApi.logout(refresh)
        } finally {
          get().clearSession()
        }
      },
    }),
    {
      name: 'gf-auth',
      partialize: (s) => ({
        user: s.user,
        access_token: s.access_token,
        refresh_token: s.refresh_token,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true)
      },
    },
  ),
)
