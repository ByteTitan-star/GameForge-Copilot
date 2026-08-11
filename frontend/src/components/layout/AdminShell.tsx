import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { ArrowLeft, Languages, Palette, Shield } from 'lucide-react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { useLocaleStore } from '@/stores/locale-store'
import { ThemePanelModal } from '@/components/theme/ThemePanelModal'
import { UserMenu } from './UserMenu'
import { AdminToastContext } from '@/pages/admin/adminToast'

const adminNavClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'gf-interactive flex shrink-0 items-center rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap',
    isActive ? 'gf-nav-link-active' : 'gf-nav-link',
  )

/**
 * 独立后台 shell：不套 AppShell、没有用户侧边栏。顶导（品牌 + 7 个 section + 主题/语言/用户），
 * main 渲染 <Outlet/>（各 section 子路由）。token 驱动，跟随全局主题。toast 由 AdminToastContext 下发，
 * 各 section 通过 useAdminToast() 推送反馈。守卫（RequireAuth + RequireAdmin）在路由层包裹本 shell。
 */
export function AdminShell() {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const setLocale = useLocaleStore((s) => s.setLocale)
  const [themeOpen, setThemeOpen] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  // toast 自动消失（4s），比旧 AdminPage 的常驻更接近生产体验
  useEffect(() => {
    if (!toast) return
    const id = window.setTimeout(() => setToast(null), 4000)
    return () => window.clearTimeout(id)
  }, [toast])

  const sections = [
    { to: '/admin/queue', label: t('adminTabQueue') },
    { to: '/admin/published', label: t('adminTabPublished') },
    { to: '/admin/users', label: t('adminTabUsers') },
    { to: '/admin/usage', label: t('adminTabUsage') },
    { to: '/admin/analytics', label: t('adminTabAnalytics') },
    { to: '/admin/audit', label: t('adminTabAudit') },
    { to: '/admin/settings', label: t('adminTabSettings') },
  ] as const

  return (
    <AdminToastContext.Provider value={setToast}>
      <div className="gf-workshop relative">
        <div className="relative z-[1] flex h-full flex-col">
          <header className="gf-glass sticky top-0 z-20 flex shrink-0 flex-wrap items-center gap-3 border-b border-[var(--gf-border)] px-4 py-2.5 backdrop-blur-xl md:px-6">
            <Link
              to="/games"
              title={t('adminBackToApp')}
              className="gf-interactive flex shrink-0 items-center gap-2.5 rounded-xl px-1.5 py-1 hover:bg-black/[0.04]"
            >
              <span className="gf-logo-badge gf-interactive grid h-8 w-8 place-items-center rounded-lg text-xs font-black">
                <Shield className="h-4 w-4" />
              </span>
              <span className="hidden sm:block">
                <span className="gf-page-body block text-sm font-semibold tracking-tight">
                  {t('adminShellTitle')}
                </span>
                <span className="gf-page-muted flex items-center gap-1 text-[10px]">
                  <ArrowLeft className="h-2.5 w-2.5" />
                  {t('adminBackToApp')}
                </span>
              </span>
            </Link>

            <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
              {sections.map((s) => (
                <NavLink key={s.to} to={s.to} className={adminNavClass}>
                  {s.label}
                </NavLink>
              ))}
            </nav>

            <div className="flex shrink-0 items-center gap-1">
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
              <UserMenu />
            </div>
          </header>

          <main className="gf-main-canvas relative min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-8 md:py-8">
              {toast ? (
                <p
                  role="status"
                  className="gf-banner-info gf-toast-in mb-5 rounded-xl px-4 py-2.5 text-sm"
                >
                  {toast}
                </p>
              ) : null}
              <Outlet />
            </div>
          </main>
        </div>

        <ThemePanelModal open={themeOpen} onClose={() => setThemeOpen(false)} />
      </div>
    </AdminToastContext.Provider>
  )
}
