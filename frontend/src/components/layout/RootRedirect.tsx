import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth-store'

/** 裸路径 `/` 统一进入营销首页；已登录用户可在 /home 再进入各工作台页面 */
export function RootRedirect() {
  const hydrated = useAuthStore((s) => s.hydrated)

  if (!hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a] text-white/60">
        Loading…
      </div>
    )
  }

  return <Navigate to="/home" replace />
}
