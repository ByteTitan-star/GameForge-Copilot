import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth-store'

/** 裸域名 `/` 不直接展示页面：已登录进工作台，未登录进营销首页 `/home` */
export function RootRedirect() {
  const hydrated = useAuthStore((s) => s.hydrated)
  const token = useAuthStore((s) => s.access_token)

  if (!hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a] text-white/60">
        Loading…
      </div>
    )
  }

  return <Navigate to={token ? '/games' : '/home'} replace />
}
