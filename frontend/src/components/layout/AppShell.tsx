import { useEffect, useState } from 'react'
import { NavLink, Outlet, Link, useLocation } from 'react-router-dom'
import { Gamepad2, Hammer, Compass, Languages, Palette, PanelLeftClose, PanelLeftOpen, Settings, Shield } from 'lucide-react'
import { Role } from '@/api/enums'
import { isTrialUser } from '@/lib/trial'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { useAuthStore } from '@/stores/auth-store'
import { useLocaleStore } from '@/stores/locale-store'
import { useSidebarStore } from '@/stores/sidebar-store'
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

const navLinkCollapsedClass = 'justify-center px-0'

const iconButtonClass =
  'gf-interactive gf-text-accent grid h-9 w-9 cursor-pointer place-items-center rounded-lg transition hover:bg-black/[0.04]'

export function AppShell() {
  const t = useT()
  const location = useLocation()
  const isForge = location.pathname.startsWith('/forge')
  const isDiscover = location.pathname.startsWith('/discover')
  const locale = useLocaleStore((s) => s.locale)
  const setLocale = useLocaleStore((s) => s.setLocale)
  const collapsed = useSidebarStore((s) => s.collapsed)
  const toggleSidebar = useSidebarStore((s) => s.toggle)
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
    <div className="gf-workshop relative" data-collapsed={collapsed ? 'true' : 'false'}>
      <ThemeBackground />
      <aside className="gf-sidebar flex flex-col border-r px-3 py-4 backdrop-blur-xl">
        <Link
          to="/home"
          title={t('backToHome')}
          className={cn(
            'gf-interactive flex items-center gap-2.5 rounded-xl px-2 py-1.5 hover:bg-black/[0.03]',
            collapsed && 'justify-center px-0',
          )}
        >
          <span className="gf-logo-badge gf-interactive grid h-9 w-9 shrink-0 place-items-center rounded-xl text-sm font-black">
            GF
          </span>
          {collapsed ? null : (
            <span>
              <span className="gf-page-body block text-sm font-semibold tracking-tight">GameForge</span>
              <span className="gf-page-muted block text-[10px]">{t('home')}</span>
            </span>
          )}
        </Link>

        <button
          type="button"
          title={collapsed ? t('expandSidebar') : t('collapseSidebar')}
          aria-label={collapsed ? t('expandSidebar') : t('collapseSidebar')}
          aria-expanded={!collapsed}
          onClick={toggleSidebar}
          className={cn(
            'gf-interactive gf-page-muted mt-3 flex cursor-pointer items-center justify-center gap-2 rounded-lg px-2 py-1.5 text-xs transition hover:bg-black/[0.04] hover:text-[var(--gf-text)]',
            collapsed && 'px-0',
          )}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          {collapsed ? null : <span>{t('collapseSidebar')}</span>}
        </button>

        <nav className="mt-6 flex flex-1 flex-col gap-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              title={collapsed ? label : undefined}
              className={({ isActive }) => cn(navLinkClass({ isActive }), collapsed && navLinkCollapsedClass)}
              end={to === '/games'}
            >
              <Icon className="h-4 w-4 shrink-0 opacity-80" />
              {collapsed ? null : label}
            </NavLink>
          ))}
          {user?.role === Role.admin ? (
            <NavLink
              to="/admin"
              title={collapsed ? t('admin') : undefined}
              className={({ isActive }) => cn(navLinkClass({ isActive }), collapsed && navLinkCollapsedClass)}
            >
              <Shield className="h-4 w-4 shrink-0 opacity-80" />
              {collapsed ? null : t('admin')}
            </NavLink>
          ) : null}
        </nav>

        <div className="gf-border-subtle mt-auto space-y-3 border-t pt-4">
          <div className={cn('flex items-center justify-between px-1', collapsed && 'flex-col gap-2 px-0')}>
            <NotificationBell />
            <div className={cn('flex items-center gap-1', collapsed && 'flex-col gap-2')}>
              <button
                type="button"
                title={t('themeTitle')}
                aria-label={t('themeTitle')}
                onClick={() => setThemeOpen(true)}
                className={iconButtonClass}
              >
                <Palette className="h-4 w-4" />
              </button>
              <button
                type="button"
                title={locale === 'zh' ? t('switchToEnglish') : t('switchToChinese')}
                aria-label={locale === 'zh' ? t('switchToEnglish') : t('switchToChinese')}
                onClick={() => setLocale(locale === 'zh' ? 'en' : 'zh')}
                className={cn(iconButtonClass, 'gf-page-muted hover:text-[var(--gf-text)]')}
              >
                <Languages className="h-4 w-4" />
              </button>
            </div>
          </div>
          <UserMenu collapsed={collapsed} />
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
              : isDiscover
                ? 'overflow-y-auto'
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
