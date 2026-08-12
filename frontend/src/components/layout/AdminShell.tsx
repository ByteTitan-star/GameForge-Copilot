import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  ArrowLeft,
  BarChart3,
  Languages,
  ListChecks,
  Menu,
  Package,
  Palette,
  ScrollText,
  Settings,
  Shield,
  TrendingUp,
  Users,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { useLocaleStore } from '@/stores/locale-store'
import { ThemePanelModal } from '@/components/theme/ThemePanelModal'
import { UserMenu } from './UserMenu'
import { AdminToastContext } from '@/pages/admin/adminToast'

type Section = {
  to: string
  label: string
  title: string
  subtitle: string
  icon: LucideIcon
}

const sidebarLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'gf-interactive flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium',
    isActive ? 'gf-nav-link-active' : 'gf-nav-link',
  )

/**
 * 独立后台 shell：不套 AppShell。左侧固定侧边栏（品牌 + 7 个 section + 主题/语言/用户）
 * + 右侧主区（topbar 当前 section 标题 + Outlet）。
 *
 * token 驱动，跟随全局主题；外层 .gf-admin 标记类触发亮色 SaaS 质感层（index.css）。
 * 桌面端 sidebar 常驻（.gf-sidebar 已有基建）；移动端 <1024px 抽屉式（.gf-admin-sidebar
 * + is-open + overlay）。守卫（RequireAuth + RequireAdmin）在路由层包裹本 shell。
 * toast 由 AdminToastContext 下发，各 section 通过 useAdminToast() 推送反馈。
 */
export function AdminShell() {
  const t = useT()
  const location = useLocation()
  const locale = useLocaleStore((s) => s.locale)
  const setLocale = useLocaleStore((s) => s.setLocale)
  const [themeOpen, setThemeOpen] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // toast 自动消失（4s）
  useEffect(() => {
    if (!toast) return
    const id = window.setTimeout(() => setToast(null), 4000)
    return () => window.clearTimeout(id)
  }, [toast])

  // 路由切换时收起移动端抽屉
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  const sections: Section[] = [
    { to: '/admin/queue', label: t('adminTabQueue'), title: t('adminQueueTitle'), subtitle: t('adminQueueSubtitle'), icon: ListChecks },
    { to: '/admin/published', label: t('adminTabPublished'), title: t('adminPublishedTitle'), subtitle: t('adminPublishedSubtitle'), icon: Package },
    { to: '/admin/users', label: t('adminTabUsers'), title: t('adminUsersTitle'), subtitle: t('adminUsersSubtitle'), icon: Users },
    { to: '/admin/usage', label: t('adminTabUsage'), title: t('adminUsageTitle'), subtitle: t('adminUsageSubtitle'), icon: BarChart3 },
    { to: '/admin/analytics', label: t('adminTabAnalytics'), title: t('adminAnalyticsTitle'), subtitle: t('adminAnalyticsSubtitle'), icon: TrendingUp },
    { to: '/admin/audit', label: t('adminTabAudit'), title: t('adminAuditTitle'), subtitle: t('adminAuditSubtitle'), icon: ScrollText },
    { to: '/admin/settings', label: t('adminTabSettings'), title: t('adminSettingsTitle'), subtitle: t('adminSettingsSubtitle'), icon: Settings },
  ]

  // 当前 section 标题（fallback 到管理后台总标题）
  const current = sections.find((s) => location.pathname.startsWith(s.to))

  const sidebarBrand = (
    <Link
      to="/games"
      title={t('adminBackToApp')}
      className="gf-interactive flex shrink-0 items-center gap-2.5 rounded-xl px-2 py-1.5 hover:bg-black/[0.03]"
    >
      <span className="gf-logo-badge gf-interactive grid h-9 w-9 place-items-center rounded-xl text-sm font-black">
        <Shield className="h-4 w-4" />
      </span>
      <span>
        <span className="gf-page-body block text-sm font-semibold tracking-tight">
          {t('adminShellTitle')}
        </span>
        <span className="gf-page-muted flex items-center gap-1 text-[10px]">
          <ArrowLeft className="h-2.5 w-2.5" />
          {t('adminBackToApp')}
        </span>
      </span>
    </Link>
  )

  const sidebarContent = (
    <>
      {sidebarBrand}
      <nav className="mt-8 flex flex-1 flex-col gap-1">
        {sections.map((s) => (
          <NavLink key={s.to} to={s.to} className={sidebarLinkClass}>
            <s.icon className="h-4 w-4 shrink-0 opacity-80" />
            {s.label}
          </NavLink>
        ))}
      </nav>
      <div className="gf-border-subtle mt-auto space-y-3 border-t pt-4">
        <div className="flex items-center justify-between px-1">
          <span className="gf-page-muted text-[10px] font-medium tracking-wider uppercase">
            {t('admin')}
          </span>
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
    </>
  )

  return (
    <AdminToastContext.Provider value={setToast}>
      <div className="gf-workshop gf-admin">
        {/* 侧边栏：桌面常驻（.gf-sidebar fixed 基建）；移动端 <1024px 抽屉（CSS
            .gf-admin-sidebar 默认 translateX(-100%)，is-open 滑入）。一个 aside，
            通过 CSS 断点切换两种形态，避免重复渲染。 */}
        {sidebarOpen ? (
          <button
            type="button"
            aria-label={t('cancel')}
            className="gf-admin-overlay lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        ) : null}
        <aside
          className={cn(
            'gf-sidebar gf-admin-sidebar flex flex-col border-r px-3 py-4 backdrop-blur-xl',
            sidebarOpen && 'is-open',
          )}
        >
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            aria-label={t('cancel')}
            className="gf-interactive gf-page-muted absolute right-2 top-2 grid h-8 w-8 cursor-pointer place-items-center rounded-lg transition hover:bg-black/[0.04] lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
          {sidebarContent}
        </aside>

        <div className="gf-shell-main relative z-[1] flex flex-col">
          <header className="gf-main-canvas sticky top-0 z-20 flex shrink-0 items-center gap-3 border-b border-[var(--gf-border)] bg-white/80 px-4 py-3 backdrop-blur-xl md:px-8">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              aria-label={t('admin')}
              className="gf-interactive gf-page-muted grid h-9 w-9 cursor-pointer place-items-center rounded-lg transition hover:bg-black/[0.04] hover:text-[var(--gf-text)] lg:hidden"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <h2 className="gf-page-title leading-tight">{current?.title ?? t('adminShellTitle')}</h2>
              {current ? <p className="gf-page-subtitle mt-0.5 hidden sm:block">{current.subtitle}</p> : null}
            </div>
          </header>

          <main className="gf-main-canvas relative min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-[1280px] px-4 py-6 md:px-8 md:py-8">
              {toast ? (
                <p role="status" className="gf-banner-info gf-toast-in mb-5 rounded-xl px-4 py-2.5 text-sm">
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
