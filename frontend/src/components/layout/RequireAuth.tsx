import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth-store'

export function RequireAuth() {
  const location = useLocation()
  const hydrated = useAuthStore((s) => s.hydrated)
  const token = useAuthStore((s) => s.access_token)
  const email = useAuthStore((s) => s.user?.email)
  const emailVerified = useAuthStore((s) => s.user?.email_verified)

  if (!hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f0f0f0] text-[#5E6470]">
        Loading…
      </div>
    )
  }

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  // 未验证邮箱：引导到验证页（试用/OAuth 账号已 verified，不受影响）
  if (emailVerified === false) {
    return <Navigate to="/verify-email" replace state={{ email }} />
  }

  return <Outlet />
}
