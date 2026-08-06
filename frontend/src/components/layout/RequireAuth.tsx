import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth-store'

export function RequireAuth() {
  const location = useLocation()
  const hydrated = useAuthStore((s) => s.hydrated)
  const token = useAuthStore((s) => s.access_token)

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

  return <Outlet />
}
