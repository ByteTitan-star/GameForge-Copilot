import { Navigate, Outlet } from 'react-router-dom'
import { Role } from '@/api/enums'
import { useAuthStore } from '@/stores/auth-store'

export function RequireAdmin() {
  const user = useAuthStore((s) => s.user)
  if (user?.role !== Role.admin) {
    return <Navigate to="/games" replace />
  }
  return <Outlet />
}
