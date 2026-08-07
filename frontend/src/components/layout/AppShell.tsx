import { NavLink, Outlet, Link, useLocation } from 'react-router-dom'
import { Gamepad2, Hammer, Languages, Settings, Shield } from 'lucide-react'
import { Role } from '@/api/enums'
import { isTrialUser } from '@/lib/trial'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { useAuthStore } from '@/stores/auth-store'
import { useLocaleStore } from '@/stores/locale-store'
import { NotificationBell } from './NotificationBell'

const iconLink = ({ isActive }: { isActive: boolean }) =>
  cn(
    'grid h-10 w-10 place-items-center rounded-xl transition-all duration-200',
    isActive
      ? 'bg-[#ff705c]/15 text-[#ff8a79] shadow-[0_0_16px_rgba(255,112,92,0.08)]'
      : 'text-white/45 hover:bg-white/[0.06] hover:text-white/90',
  )

export function AppShell() {
  const t = useT()
  const location = useLocation()
  const forgeMode = location.pathname.startsWith('/forge')
  const locale = useLocaleStore((s) => s.locale)
  const setLocale = useLocaleStore((s) => s.setLocale)
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const trial = isTrialUser(user)
  const initial = (user?.email?.[0] ?? 'G').toUpperCase()

  return (
    <div className={cn('flex min-h-screen', forgeMode ? 'bg-[#e7ebee] text-[#1d2329]' : 'bg-[#0B0E14] text-white')}>
      <aside className="sticky top-0 z-40 flex h-screen w-[60px] shrink-0 flex-col items-center border-r border-white/[0.06] bg-[#131821]/90 py-4 backdrop-blur-xl">
        <Link
          to="/"
          title="GameForge"
          className="grid h-10 w-10 place-items-center rounded-xl bg-[#ff705c] text-[11px] font-black tracking-tighter text-[#24110e] shadow-[0_0_20px_rgba(255,112,92,0.18)]"
        >
          GF
        </Link>

        <nav className="mt-8 flex flex-1 flex-col items-center gap-2">
          <NavLink to="/games" className={iconLink} title={t('dashboard')}>
            <Gamepad2 className="h-4 w-4" />
          </NavLink>
          <NavLink to="/forge" className={iconLink} title={t('forge')}>
            <Hammer className="h-4 w-4" />
          </NavLink>
          <NavLink to="/settings" className={iconLink} title={t('settings')}>
            <Settings className="h-4 w-4" />
          </NavLink>
          {user?.role === Role.admin ? (
            <NavLink to="/admin" className={iconLink} title={t('admin')}>
              <Shield className="h-4 w-4" />
            </NavLink>
          ) : null}
        </nav>

        <div className="mt-auto flex flex-col items-center gap-3">
          <NotificationBell />
          <div
            className="flex items-center gap-1.5 rounded-full bg-white/[0.04] px-2 py-1"
            title={t('liveApiTitle')}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            <span className="font-mono text-[9px] tracking-wider text-white/45 uppercase">
              {t('liveApi')}
            </span>
          </div>

          <button
            type="button"
            title={locale === 'zh' ? t('switchToEnglish') : t('switchToChinese')}
            aria-label={locale === 'zh' ? t('switchToEnglish') : t('switchToChinese')}
            onClick={() => setLocale(locale === 'zh' ? 'en' : 'zh')}
            className="grid h-9 w-9 cursor-pointer place-items-center rounded-xl text-white/50 transition hover:bg-white/[0.08] hover:text-white"
          >
            <Languages className="h-4 w-4" />
          </button>

          <button
            type="button"
            title={`${user?.email ?? ''} · ${t('logout')}`}
            onClick={() => void logout()}
            className="grid h-9 w-9 cursor-pointer place-items-center rounded-full bg-[#5271ff]/20 text-xs font-semibold text-[#aebcff] ring-1 ring-white/15 transition hover:bg-[#5271ff]/30"
          >
            {initial}
          </button>
        </div>
      </aside>

      <div className="relative min-w-0 flex-1">
        <div
          aria-hidden
          className={cn('pointer-events-none absolute inset-y-0 left-0 w-px', forgeMode ? 'bg-black/[0.08]' : 'bg-white/[0.08]')}
        />
        {trial ? (
          <div
            role="status"
            className={cn(
              'sticky top-0 z-30 border-b px-4 py-2 text-center text-xs leading-relaxed md:px-8',
              forgeMode
                ? 'border-amber-500/25 bg-amber-50 text-amber-900'
                : 'border-amber-400/25 bg-amber-400/10 text-amber-100',
            )}
          >
            {t('trialBanner')}
          </div>
        ) : null}
        <main className="relative mx-auto w-full max-w-[1600px] px-4 py-5 md:px-8 md:py-7">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
