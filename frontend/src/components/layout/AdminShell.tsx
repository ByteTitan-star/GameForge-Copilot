import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  ArrowLeft,
  BarChart3,
  Languages,
  LayoutDashboard,
  ListChecks,
  Menu,
  Package,
  Palette,
  ScrollText,
  Settings,
  TrendingUp,
  Users,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { useLocaleStore } from '@/stores/locale-store'
import { ThemePanelModal } from '@/components/theme/ThemePanelModal'
import { FlowerLogo } from '@/components/admin/FlowerLogo'
import { UserMenu } from './UserMenu'
import { AdminToastContext, type ToastVariant } from '@/pages/admin/adminToast'

type Section = {
  to: string
  /** 是否为概览（精确匹配 /admin，不参与 startsWith） */
  exact?: boolean
  label: string
  title: string
  titleAccent?: string
  subtitle: string
  icon: LucideIcon
}

const sidebarLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'gf-interactive flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
    isActive ? 'gf-admin-nav-active' : 'gf-admin-nav',
  )

/**
 * 独立后台 shell（Convix 风）：不套 AppShell。左侧固定侧边栏（橙色 8 瓣花品牌 +
 * Overview + 7 个 section + 主题/语言/用户）+ 右侧主区（浮动胶囊 topbar + Outlet）。
 *
 * admin 作用域（.gf-admin）强制橙色主题（index.css 的 !important token 覆盖），
 * 与主站/forge/games 的用户自选主题解耦。桌面端 sidebar 常驻；移动端 <1024px 抽屉
 * （.gf-admin-sidebar + is-open + overlay），抽屉打开时主内容区 inert 防止键盘焦点逃逸。
 * 守卫（RequireAuth + RequireAdmin）在路由层包裹本 shell。
 * toast 由 AdminToastContext 下发，各 section 通过 useAdminToast() 推送反馈。
 */
export function AdminShell() {
  const t = useT()
  const location = useLocation()
  const locale = useLocaleStore((s) => s.locale)
  const setLocale = useLocaleStore((s) => s.setLocale)
  const [themeOpen, setThemeOpen] = useState(false)
  const [toast, setToast] = useState<{ message: string; variant: ToastVariant } | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // toast 推送：默认 info（role=status）。失败路径传 'error'（role=alert）让屏幕阅读器立即播报。
  const pushToast = useCallback((message: string, variant: ToastVariant = 'info') => {
    setToast({ message, variant })
  }, [])

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

  // 抽屉打开时锁背景滚动
  useEffect(() => {
    if (!sidebarOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [sidebarOpen])

  const sections: Section[] = [
    { to: '/admin', exact: true, label: t('adminTabOverview'), title: t('adminOverviewHeaderTitle'), subtitle: t('adminOverviewSubtitle'), icon: LayoutDashboard },
    { to: '/admin/queue', label: t('adminTabQueue'), title: t('adminQueueTitle'), subtitle: t('adminQueueSubtitle'), icon: ListChecks },
    { to: '/admin/published', label: t('adminTabPublished'), title: t('adminPublishedTitle'), subtitle: t('adminPublishedSubtitle'), icon: Package },
    { to: '/admin/users', label: t('adminTabUsers'), title: t('adminUsersTitle'), subtitle: t('adminUsersSubtitle'), icon: Users },
    { to: '/admin/usage', label: t('adminTabUsage'), title: t('adminUsageTitle'), subtitle: t('adminUsageSubtitle'), icon: BarChart3 },
    { to: '/admin/analytics', label: t('adminTabAnalytics'), title: t('adminAnalyticsTitle'), subtitle: t('adminAnalyticsSubtitle'), icon: TrendingUp },
    { to: '/admin/audit', label: t('adminTabAudit'), title: t('adminAuditTitle'), subtitle: t('adminAuditSubtitle'), icon: ScrollText },
    { to: '/admin/settings', label: t('adminTabSettings'), title: t('adminSettingsTitle'), subtitle: t('adminSettingsSubtitle'), icon: Settings },
  ]

  // 当前 section 标题（Overview 精确匹配，其余 startsWith）
  const current = sections.find((s) =>
    s.exact ? location.pathname === s.to : location.pathname.startsWith(s.to) && s.to !== '/admin',
  ) ?? sections[0]

  const sidebarBrand = (
    <Link
      to="/games"
      title={t('adminBackToApp')}
      className="gf-interactive flex shrink-0 items-center gap-2.5 rounded-xl px-2 py-1.5 transition-colors hover:bg-black/[0.03]"
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white shadow-sm ring-1 ring-black/5">
        <FlowerLogo className="h-6 w-6" />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold tracking-tight text-[var(--gf-text)]">
          {t('adminShellTitle')}
        </span>
        <span className="gf-admin-serif-italic block text-[13px] leading-tight text-[#ef4d23]">
          {t('adminShellTagline')}
        </span>
      </span>
    </Link>
  )

  const sidebarContent = (
    <>
      {sidebarBrand}
      <nav aria-label={t('admin')} className="mt-8 flex flex-1 flex-col gap-1">
        {sections.map((s) => (
          <NavLink
            key={s.to}
            to={s.to}
            end={s.exact}
            className={sidebarLinkClass}
          >
            <s.icon className="h-4 w-4 shrink-0" />
            {s.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto space-y-3 border-t border-[var(--gf-border)] pt-4">
        <div className="flex items-center justify-between px-1">
          <span className="text-[10px] font-medium uppercase tracking-wider text-neutral-400">
            {t('admin')}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              title={t('themeTitle')}
              aria-label={t('themeTitle')}
              onClick={() => setThemeOpen(true)}
              className="gf-interactive grid h-9 w-9 cursor-pointer place-items-center rounded-lg text-[#ef4d23] transition hover:bg-black/[0.04]"
            >
              <Palette className="h-4 w-4" />
            </button>
            <button
              type="button"
              title={locale === 'zh' ? t('switchToEnglish') : t('switchToChinese')}
              aria-label={locale === 'zh' ? t('switchToEnglish') : t('switchToChinese')}
              onClick={() => setLocale(locale === 'zh' ? 'en' : 'zh')}
              className="gf-interactive grid h-9 w-9 cursor-pointer place-items-center rounded-lg text-neutral-500 transition hover:bg-black/[0.04] hover:text-[var(--gf-text)]"
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
    <AdminToastContext.Provider value={pushToast}>
      <div className="gf-admin gf-admin-frame min-h-screen bg-[#ededed] p-3 sm:p-4">
        {/* Convix 风大圆角容器：侧边栏 + 主区一起被圆角裁切 */}
        <div className="relative flex h-[calc(100vh-24px)] w-full overflow-hidden rounded-2xl bg-[var(--gf-admin-bg-soft)] sm:h-[calc(100vh-32px)] sm:rounded-3xl">
          {/* 移动端遮罩 + 主区 inert（抽屉打开时锁键盘焦点在抽屉内） */}
          {sidebarOpen ? (
            <button
              type="button"
              aria-label={t('adminCloseSidebar')}
              className="gf-admin-overlay absolute inset-0 z-40 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            />
          ) : null}
          <aside
            className={cn(
              'gf-admin-sidebar relative z-50 flex w-64 shrink-0 flex-col bg-white px-3 py-4 shadow-sm',
              sidebarOpen && 'is-open',
            )}
          >
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              aria-label={t('adminCloseSidebar')}
              className="gf-interactive absolute right-2 top-2 grid h-8 w-8 cursor-pointer place-items-center rounded-lg text-neutral-500 transition hover:bg-black/[0.04] lg:hidden"
            >
              <X className="h-4 w-4" />
            </button>
            {sidebarContent}
          </aside>

          <div
            className="gf-shell-main relative z-[1] flex min-w-0 flex-1 flex-col"
            // 抽屉打开时，主内容区 inert，键盘焦点锁在侧边栏抽屉内
            inert={sidebarOpen ? true : undefined}
          >
            {/* 浮动胶囊 topbar：当前 section 标题（Inter 半粗 + Serif 斜体点睛）+ 返回主站 */}
            <header className="flex items-center gap-3 border-b border-black/5 bg-white/80 px-4 py-3 backdrop-blur-xl md:px-8">
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                aria-label={t('admin')}
                className="gf-interactive grid h-9 w-9 cursor-pointer place-items-center rounded-lg text-neutral-500 transition hover:bg-black/[0.04] hover:text-[var(--gf-text)] lg:hidden"
              >
                <Menu className="h-4 w-4" />
              </button>
              <div className="min-w-0 flex-1">
                <h2 className="flex items-center gap-2 truncate text-[15px] font-semibold leading-tight text-[var(--gf-text)]">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#ef4d23]" />
                  {current.title}
                  {current.titleAccent ? (
                    <span className="gf-admin-serif-italic text-[#ef4d23]">{current.titleAccent}</span>
                  ) : null}
                </h2>
                {current ? <p className="mt-0.5 truncate text-xs text-neutral-500">{current.subtitle}</p> : null}
              </div>
              <Link
                to="/games"
                className="gf-interactive gf-admin-cta-btn hidden h-9 shrink-0 items-center gap-1.5 px-4 text-xs sm:inline-flex"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                {t('adminBackToApp')}
              </Link>
            </header>

            <main className="relative min-h-0 flex-1 overflow-y-auto bg-[#ededed]">
              <div className="mx-auto w-full max-w-[1280px] px-4 py-6 md:px-8 md:py-8">
                {toast ? (
                  <p
                    role={toast.variant === 'error' ? 'alert' : 'status'}
                    className={cn(
                      'gf-toast-in mb-5 rounded-xl px-4 py-2.5 text-sm',
                      toast.variant === 'error' ? 'gf-banner-error' : 'gf-banner-info',
                    )}
                  >
                    {toast.message}
                  </p>
                ) : null}
                <Outlet />
              </div>
            </main>
          </div>
        </div>

        <ThemePanelModal open={themeOpen} onClose={() => setThemeOpen(false)} />
      </div>
    </AdminToastContext.Provider>
  )
}
