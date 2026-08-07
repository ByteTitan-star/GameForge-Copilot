import { useEffect, useState } from 'react'
import { NavLink, Outlet, Link, useLocation } from 'react-router-dom'
import { Gamepad2, Hammer, Compass, Languages, Palette, Settings, Shield } from 'lucide-react'
import { Role } from '@/api/enums'
import { isTrialUser } from '@/lib/trial'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { useAuthStore } from '@/stores/auth-store'
import { useLocaleStore } from '@/stores/locale-store'
import { ThemeBackground } from '@/components/theme/ThemeBackground'
import { ThemePanelModal } from '@/components/theme/ThemePanelModal'
import { NotificationBell } from './NotificationBell'
import { UserMenu } from './UserMenu'
import { OnboardingModal } from '@/components/onboarding/OnboardingModal'
import { ActiveRunBanner } from '@/components/layout/ActiveRunBanner'
import { isOnboardingDone } from '@/lib/onboarding-storage'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'gf-interactive flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium',
    isActive ? 'gf-nav-link-active' : 'gf-nav-link',
  )

export function AppShell() {
  const t = useT()
  const location = useLocation()
  const isForge = location.pathname.startsWith('/forge')
  const locale = useLocaleStore((s) => s.locale)
  const setLocale = useLocaleStore((s) => s.setLocale)
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.access_token)
  const trial = isTrialUser(user)
  const [themeOpen, setThemeOpen] = useState(false)
  const [onboardingOpen, setOnboardingOpen] = useState(false)

  useEffect(() => {
    if (token && user && !trial && !isOnboardingDone()) {
      setOnboardingOpen(true)
    }
  }, [token, user, trial])

  const navItems = [
    { to: '/games', icon: Gamepad2, label: t('games') },
    { to: '/forge', icon: Hammer, label: t('forge') },
    { to: '/discover', icon: Compass, label: t('discover') },
    { to: '/settings', icon: Settings, label: t('settings') },
  ] as const

  return (
    <div className="gf-workshop relative">
      <ThemeBackground />
      <aside className="gf-sidebar flex flex-col border-r px-3 py-4 backdrop-blur-xl">
        <Link
          to="/home"
          title={t('backToHome')}
          className="gf-interactive flex items-center gap-2.5 rounded-xl px-2 py-1.5 hover:bg-black/[0.03]"
        >
          <span className="gf-logo-badge gf-interactive grid h-9 w-9 place-items-center rounded-xl text-sm font-black">
            GF
          </span>
          <span>
            <span className="gf-page-body block text-sm font-semibold tracking-tight">GameForge</span>
            <span className="gf-page-muted block text-[10px]">{t('home')}</span>
          </span>
        </Link>

        <nav className="mt-8 flex flex-1 flex-col gap-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} className={navLinkClass} end={to === '/games'}>
              <Icon className="h-4 w-4 shrink-0 opacity-80" />
              {label}
            </NavLink>
          ))}
          {user?.role === Role.admin ? (
            <NavLink to="/admin" className={navLinkClass}>
              <Shield className="h-4 w-4 shrink-0 opacity-80" />
              {t('admin')}
            </NavLink>
          ) : null}
        </nav>

        <div className="gf-border-subtle mt-auto space-y-3 border-t pt-4">
          <div className="flex items-center justify-between px-1">
            <NotificationBell />
            <div className="flex items-center gap-1">
              <button
                type="button"
                title={t('themeTitle')}
                aria-label={t('themeTitle')}
                onClick={() => setThemeOpen(true)}
                className="gf-interactive gf-text-accent grid h-9 w-9 cursor-pointer place-items-center rounded-lg transition hover:bg-black/[0.04]"
              >
                <Palette className="h-4 w-4" />
              </button>
              <button
                type="button"
                title={locale === 'zh' ? t('switchToEnglish') : t('switchToChinese')}
                aria-label={locale === 'zh' ? t('switchToEnglish') : t('switchToChinese')}
                onClick={() => setLocale(locale === 'zh' ? 'en' : 'zh')}
                className="gf-interactive gf-page-muted grid h-9 w-9 cursor-pointer place-items-center rounded-lg transition hover:bg-black/[0.04] hover:text-[var(--gf-text)]"
              >
                <Languages className="h-4 w-4" />
              </button>
            </div>
          </div>
          <UserMenu />
        </div>
      </aside>

      <div className="gf-shell-main relative z-[1] flex flex-col">
        {trial ? (
          <div
            role="status"
            className="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs leading-relaxed text-amber-900 md:px-8"
          >
            {t('trialBanner')}
          </div>
        ) : null}

        {!trial ? <ActiveRunBanner /> : null}

        <main
          className={cn(
            'gf-main-canvas relative min-h-0 flex-1',
            isForge
              ? 'gf-main-canvas--forge flex flex-col p-3 md:p-4 lg:p-5'
              : 'mx-auto w-full max-w-[1400px] overflow-y-auto px-4 py-6 md:px-8 md:py-8',
          )}
        >
          <Outlet />
        </main>
      </div>

      <ThemePanelModal open={themeOpen} onClose={() => setThemeOpen(false)} />
      <OnboardingModal open={onboardingOpen} onClose={() => setOnboardingOpen(false)} />
    </div>
  )
}
