import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { RequireAdmin } from '@/components/layout/RequireAdmin'
import { RequireAuth } from '@/components/layout/RequireAuth'
import { AdminPage } from '@/pages/admin/AdminPage'
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
import { CreatorPage } from '@/pages/creator/CreatorPage'
import { SettingsPage } from '@/pages/settings/SettingsPage'
import { ToonHubHero } from '@/pages/preview/ToonHubHero'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/home" element={<LandingPage />} />
      <Route path="/discover" element={<DiscoverPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      {/* 邮件模板链接：frontend_base_url/reset-password?token=… */}
      <Route path="/reset-password" element={<ForgotPasswordPage />} />
      <Route path="/oauth/callback" element={<OAuthCallbackPage />} />
      <Route path="/play/:slug" element={<PlayPage />} />
      <Route path="/u/:handle" element={<CreatorPage />} />
      <Route path="/draft/:gameId/:version" element={<DraftPlayPage />} />
      <Route path="/preview/toonhub" element={<ToonHubHero />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/games" element={<GamesPage />} />
          <Route path="/forge" element={<ForgePage />} />
          <Route path="/forge/:gameId" element={<ForgePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route element={<RequireAdmin />}>
            <Route path="/admin" element={<AdminPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  )
}
