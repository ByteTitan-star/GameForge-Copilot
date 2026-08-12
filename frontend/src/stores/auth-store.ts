import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '@/api/auth'
import type { User } from '@/api/types'
import { isTrialUser } from '@/lib/trial'
import { queryClient } from '@/lib/query-client'

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
      setSession: ({ user, access_token, refresh_token }) => {
        // 试用会话只留内存：清掉可能残留的持久化登录态
        if (isTrialUser(user)) {
          try {
            localStorage.removeItem('gf-auth')
          } catch {
            /* ignore */
          }
        }
        set({ user, access_token, refresh_token })
      },
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
          // 先取消所有在飞请求，避免旧账号的 401-refresh 竞态回流清掉新会话；
          // 再清空缓存，避免换号后新账号命中旧账号 ['notifications'] 等无 user 维度的 key。
          // cancelQueries 可能因「无查询可取消」抛出，属预期，显式兜住。
          await queryClient.cancelQueries().catch(() => {})
          queryClient.clear()
          get().clearSession()
        }
      },
    }),
    {
      name: 'gf-auth',
      partialize: (s) => {
        // 试用账号不写入 localStorage
        if (isTrialUser(s.user)) return {}
        return {
          user: s.user,
          access_token: s.access_token,
          refresh_token: s.refresh_token,
        }
      },
      onRehydrateStorage: () => (state) => {
        // 历史误持久化的试用会话：丢弃
        if (state && isTrialUser(state.user)) {
          state.clearSession()
        }
        state?.setHydrated(true)
      },
    },
  ),
)
