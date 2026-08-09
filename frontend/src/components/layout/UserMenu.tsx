import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronUp, Home, LogOut, Settings, Shield, User } from 'lucide-react'
import { Role } from '@/api/enums'
import { cn } from '@/lib/cn'
import { isTrialUser } from '@/lib/trial'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'

export function UserMenu() {
  const t = useT()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const trial = isTrialUser(user)
  const initial = (user?.email?.[0] ?? 'G').toUpperCase()

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  if (!user) return null

  return (
    <div ref={rootRef} className="relative w-full">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'gf-interactive gf-menu-trigger gf-border-subtle flex w-full cursor-pointer items-center gap-3 rounded-xl border bg-[var(--gf-surface)] px-3 py-2.5 text-left transition',
          open && 'gf-menu-trigger-open',
        )}
      >
        <span className="gf-avatar-ring grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-semibold">
          {initial}
        </span>
        <span className="min-w-0 flex-1">
          <span className="gf-page-body block truncate text-sm">{user.email}</span>
          <span className="gf-page-muted block text-[11px]">
            {trial ? t('fillTrialPreview') : user.role === Role.admin ? t('roleAdmin') : t('roleUser')}
          </span>
        </span>
        <ChevronUp className={cn('gf-page-muted h-4 w-4 shrink-0 transition', open ? 'rotate-0' : 'rotate-180')} />
      </button>

      {open ? (
        <div
          role="menu"
          className="gf-border-subtle absolute bottom-full left-0 z-50 mb-2 w-full overflow-hidden rounded-xl border bg-[var(--gf-surface)] py-1 shadow-[0_16px_40px_rgba(15,23,42,0.12)]"
        >
          <div className="gf-border-subtle border-b px-3 py-2.5">
            <p className="gf-page-body flex items-center gap-2 text-xs font-medium">
              <User className="gf-text-accent h-3.5 w-3.5" />
              {t('accountInfo')}
            </p>
            <p className="gf-page-muted mt-1 truncate text-[11px]">{user.email}</p>
          </div>
          <Link
            to="/home"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="gf-page-body flex cursor-pointer items-center gap-2 px-3 py-2.5 text-sm transition hover:bg-black/[0.03]"
          >
            <Home className="gf-page-muted h-4 w-4" />
            {t('home')}
          </Link>
          <Link
            to="/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="gf-page-body flex cursor-pointer items-center gap-2 px-3 py-2.5 text-sm transition hover:bg-black/[0.03]"
          >
            <Settings className="gf-page-muted h-4 w-4" />
            {t('settings')}
          </Link>
          {user.role === Role.admin ? (
            <Link
              to="/admin"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="gf-page-body flex cursor-pointer items-center gap-2 px-3 py-2.5 text-sm transition hover:bg-black/[0.03]"
            >
              <Shield className="gf-page-muted h-4 w-4" />
              {t('admin')}
            </Link>
          ) : null}
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false)
              void logout()
            }}
            className="gf-border-subtle flex w-full cursor-pointer items-center gap-2 border-t px-3 py-2.5 text-sm text-rose-600 transition hover:bg-rose-50"
          >
            <LogOut className="h-4 w-4" />
            {t('logout')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
