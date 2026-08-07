import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { Role } from '@/api/enums'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { useAuthStore } from '@/stores/auth-store'
import { ProfilePanel } from './ProfilePanel'
import { LlmConfigPanel } from './LlmConfigPanel'
import { UsagePanel } from './UsagePanel'
import { ThemePanel } from '@/components/theme/ThemePanel'

type SettingsTab = 'account' | 'profile' | 'appearance' | 'llm'

export function SettingsPage() {
  const t = useT()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.access_token)
  const location = useLocation()
  const state = location.state as {
    needVerify?: boolean
    justVerified?: boolean
    tab?: SettingsTab
  } | null
  const [tab, setTab] = useState<SettingsTab>(state?.tab ?? 'account')

  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pwdError, setPwdError] = useState('')
  const [pwdOk, setPwdOk] = useState('')
  const [pwdLoading, setPwdLoading] = useState(false)

  async function onChangePassword(e: FormEvent) {
    e.preventDefault()
    setPwdError('')
    setPwdOk('')
    if (!token) {
      setPwdError(t('loginRequired'))
      return
    }
    if (newPassword.length < 8) {
      setPwdError(t('pwdMinLength'))
      return
    }
    if (newPassword !== confirmPassword) {
      setPwdError(t('pwdMismatch'))
      return
    }
    setPwdLoading(true)
    try {
      await authApi.changePassword(oldPassword, newPassword, token)
      setPwdOk(t('pwdUpdated'))
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setPwdError(formatApiError(err, t('changePwdFailed')))
    } finally {
      setPwdLoading(false)
    }
  }

  const tabs: { id: SettingsTab; label: string }[] = [
    { id: 'account', label: t('tabAccount') },
    { id: 'profile', label: t('tabProfile') },
    { id: 'appearance', label: t('themeTab') },
    { id: 'llm', label: t('tabLlm') },
  ]

  return (
    <div className="space-y-6">
      <header>
        <h1 className="gf-page-title">{t('settings')}</h1>
        <p className="gf-page-subtitle mt-1">{t('settingsSubtitle')}</p>
      </header>

      {state?.needVerify ? (
        <p role="status" className="gf-banner-warn rounded-xl px-4 py-3 text-sm">
          {t('needVerifyBanner')}
        </p>
      ) : null}
      {state?.justVerified ? (
        <p role="status" className="gf-banner-info rounded-xl px-4 py-3 text-sm">
          {t('justVerifiedBanner')}
        </p>
      ) : null}

      <div className="gf-border-subtle flex gap-1 border-b">
        {tabs.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              'cursor-pointer border-b-2 px-4 py-2.5 text-sm font-medium transition -mb-px',
              tab === id
                ? 'gf-tab-active'
                : 'border-transparent gf-page-muted hover:text-[var(--gf-text)]',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'account' ? (
        <div className="space-y-6">
          <section className="gf-glass rounded-2xl p-5">
            <h2 className="gf-page-body text-lg">{t('accountInfo')}</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div className="gf-border-subtle flex flex-wrap items-center justify-between gap-2 rounded-xl bg-black/[0.02] px-4 py-3 ring-1 ring-[var(--gf-border)]">
                <dt className="gf-page-muted">{t('email')}</dt>
                <dd className="gf-page-body flex items-center gap-2">
                  {user?.email}
                  {user?.email_verified ? (
                    <span className="rounded-md bg-emerald-400/15 px-2 py-0.5 text-[11px] text-emerald-300 ring-1 ring-emerald-400/25">
                      {t('verified')}
                    </span>
                  ) : (
                    <span className="gf-badge-warn rounded-md px-2 py-0.5 text-[11px]">
                      {t('unverified')}
                    </span>
                  )}
                </dd>
              </div>
              <div className="gf-border-subtle flex justify-between gap-4 rounded-xl bg-black/[0.02] px-4 py-3 ring-1 ring-[var(--gf-border)]">
                <dt className="gf-page-muted">{t('roleLabel')}</dt>
                <dd className="gf-page-body">{user?.role === Role.admin ? t('roleAdmin') : t('roleUser')}</dd>
              </div>
            </dl>
            {!user?.email_verified ? (
              <div className="mt-4">
                <Button
                  type="button"
                  className="gf-btn-primary !rounded-xl !border-0 !text-sm"
                  onClick={() =>
                    navigate('/verify-email', { state: { email: user?.email } })
                  }
                >
                  {t('goVerifyEmail')}
                </Button>
              </div>
            ) : null}
          </section>

          <section className="gf-glass rounded-2xl p-5">
            <h2 className="gf-page-body text-lg">{t('changePassword')}</h2>
            <p className="gf-page-muted mt-1 text-xs">{t('changePasswordHint')}</p>
            <form className="mt-4 max-w-md space-y-3" onSubmit={onChangePassword}>
              <Input
                name="old_password"
                label={t('oldPassword')}
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
              <Input
                name="new_password"
                label={t('newPassword')}
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
              <Input
                name="confirm_password"
                label={t('confirmPassword')}
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
              {pwdError ? (
                <p role="alert" className="text-sm text-red-300">
                  {pwdError}
                </p>
              ) : null}
              {pwdOk ? (
                <p role="status" className="text-sm text-cyan-200">
                  {pwdOk}
                </p>
              ) : null}
              <Button type="submit" className="gf-btn-primary !rounded-xl !border-0" disabled={pwdLoading}>
                {pwdLoading ? t('savingPassword') : t('changePassword')}
              </Button>
            </form>
            <p className="gf-page-muted mt-3 text-xs">
              {t('forgotOldPwd')}{' '}
              <Link to="/forgot-password" className="gf-text-accent opacity-80 underline-offset-2 hover:underline">
                {t('forgot')}
              </Link>
            </p>
          </section>
        </div>
      ) : tab === 'profile' && token ? (
        <ProfilePanel accessToken={token} />
      ) : tab === 'appearance' ? (
        <ThemePanel />
      ) : (
        <div className="space-y-6">
          <LlmConfigPanel />
          <UsagePanel />
        </div>
      )}
    </div>
  )
}
