import { Navigate, Route, Routes } from 'react-router-dom'
import { AdminShell } from '@/components/layout/AdminShell'
import { AppShell } from '@/components/layout/AppShell'
import { RequireAdmin } from '@/components/layout/RequireAdmin'
import { RequireAuth } from '@/components/layout/RequireAuth'
import { AnalyticsSection } from '@/pages/admin/sections/AnalyticsSection'
import { AuditSection } from '@/pages/admin/sections/AuditSection'
import { OverviewSection } from '@/pages/admin/sections/OverviewSection'
import { PublishedSection } from '@/pages/admin/sections/PublishedSection'
import { QueueSection } from '@/pages/admin/sections/QueueSection'
import { SettingsSection } from '@/pages/admin/sections/SettingsSection'
import { UsageSection } from '@/pages/admin/sections/UsageSection'
import { UsersSection } from '@/pages/admin/sections/UsersSection'
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage'
import { LoginPage } from '@/pages/auth/LoginPage'
import { OAuthCallbackPage } from '@/pages/auth/OAuthCallbackPage'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { VerifyEmailPage } from '@/pages/auth/VerifyEmailPage'
import { DiscoverPage } from '@/pages/discover/DiscoverPage'
import { ForgePage } from '@/pages/forge/ForgePage'
import { GamesPage } from '@/pages/games/GamesPage'
import { LandingPage } from '@/pages/LandingPage'
import { RootRedirect } from '@/components/layout/RootRedirect'
import { DraftPlayPage } from '@/pages/play/DraftPlayPage'
import { PlayPage } from '@/pages/play/PlayPage'
import { TemplatePlayPage } from '@/pages/play/TemplatePlayPage'
import { CreatorPage } from '@/pages/creator/CreatorPage'
import { SettingsPage } from '@/pages/settings/SettingsPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/home" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      {/* 邮件模板链接：frontend_base_url/reset-password?token=… */}
      <Route path="/reset-password" element={<ForgotPasswordPage />} />
      <Route path="/oauth/callback" element={<OAuthCallbackPage />} />
      <Route path="/play/template/:templateId" element={<TemplatePlayPage />} />
      <Route path="/play/:slug" element={<PlayPage />} />
      <Route path="/u/:handle" element={<CreatorPage />} />
      <Route path="/draft/:gameId/:version" element={<DraftPlayPage />} />

      <Route element={<AppShell />}>
        <Route path="/discover" element={<DiscoverPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/games" element={<GamesPage />} />
          <Route path="/forge" element={<ForgePage />} />
          <Route path="/forge/:gameId" element={<ForgePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>

      {/* 独立后台 shell：双守卫 + AdminShell layout + section 子路由（URL 驱动，可分享/后退） */}
      <Route element={<RequireAuth />}>
        <Route element={<RequireAdmin />}>
          <Route path="/admin" element={<AdminShell />}>
            <Route index element={<OverviewSection />} />
            <Route path="queue" element={<QueueSection />} />
            <Route path="published" element={<PublishedSection />} />
            <Route path="users" element={<UsersSection />} />
            <Route path="usage" element={<UsageSection />} />
            <Route path="analytics" element={<AnalyticsSection />} />
            <Route path="audit" element={<AuditSection />} />
            <Route path="settings" element={<SettingsSection />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  )
}
