import { NavLink, Outlet, Link } from 'react-router-dom'
import { Gamepad2, Hammer, Settings, Shield } from 'lucide-react'
import { Role } from '@/api/enums'
import { useT } from '@/i18n/use-t'
import { env } from '@/lib/env'
import { cn } from '@/lib/cn'
import { useAuthStore } from '@/stores/auth-store'
import { Button } from '@/components/ui/button'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors duration-200',
    isActive
      ? 'bg-white/[0.1] text-white'
      : 'text-white/55 hover:bg-white/[0.06] hover:text-white/90',
  )

export function AppShell() {
  const t = useT()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  return (
    <div className="flex min-h-screen flex-col bg-[#0b0d10] text-white">
      <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#0b0d10]/90 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between gap-4 px-3 py-3 md:px-5">
          <div className="flex items-center gap-5">
            <Link
              to="/"
              className="font-mono text-sm font-semibold tracking-[0.14em] text-white/90 uppercase transition-opacity hover:opacity-80"
            >
              {t('brand')}
            </Link>
            <nav className="hidden items-center gap-0.5 md:flex">
              <NavLink to="/games" className={linkClass}>
                <Gamepad2 className="h-3.5 w-3.5 opacity-70" />
                {t('games')}
              </NavLink>
              <NavLink to="/forge" className={linkClass}>
                <Hammer className="h-3.5 w-3.5 opacity-70" />
                {t('forge')}
              </NavLink>
              <NavLink to="/settings" className={linkClass}>
                <Settings className="h-3.5 w-3.5 opacity-70" />
                {t('settings')}
              </NavLink>
              {user?.role === Role.admin ? (
                <NavLink to="/admin" className={linkClass}>
                  <Shield className="h-3.5 w-3.5 opacity-70" />
                  {t('admin')}
                </NavLink>
              ) : null}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden font-mono text-[11px] text-white/40 sm:inline">
              {user?.email}
              {!user?.email_verified ? ' · unverified' : ''}
            </span>
            <Button
              variant="ghost"
              className="!rounded-lg !px-3 !py-1.5 text-xs text-white/70 hover:text-white"
              onClick={() => void logout()}
            >
              {t('logout')}
            </Button>
          </div>
        </div>
        {env.useMock ? (
          <p className="border-t border-white/[0.04] px-3 py-1 text-center font-mono text-[10px] tracking-[0.14em] text-teal-400/50 uppercase">
            {t('mockBanner')} · demo@gameforge.dev / password123
          </p>
        ) : null}
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-3 py-4 md:px-5 md:py-5">
        <Outlet />
      </main>
    </div>
  )
}
