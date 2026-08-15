import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { AuthShell } from '@/components/auth/AuthShell'
import { OAuthButtons } from '@/components/auth/OAuthButtons'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'
import { TRIAL_EMAIL, TRIAL_PASSWORD } from '@/lib/trial'
import { useAuthStore } from '@/stores/auth-store'
import { toast } from '@/stores/toast-store'

export function LoginPage() {
  const t = useT()
  const navigate = useNavigate()
  const location = useLocation()
  const authState = location.state as {
    from?: string
    email?: string
  } | null
  const setSession = useAuthStore((s) => s.setSession)
  const [email, setEmail] = useState(authState?.email ?? '')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [loading, setLoading] = useState(false)
  const [trialLoading, setTrialLoading] = useState(false)

  useEffect(() => {
    if (authState?.email) setEmail(authState.email)
  }, [authState?.email])

  // 试用预览：直接用预置试用账号登录并跳转主界面，免去手动填表+点登录
  async function startTrialPreview() {
    setTrialLoading(true)
    try {
      const data = await authApi.login(TRIAL_EMAIL, TRIAL_PASSWORD)
      setSession({
        user: data.user,
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      })
      const from = authState?.from
      navigate(from && from !== '/login' ? from : '/games', { replace: true })
    } catch (err) {
      toast.error(formatApiError(err, t('errTrialFailed'), t))
    } finally {
      setTrialLoading(false)
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await authApi.login(email.trim(), password)
      setSession({
        user: data.user,
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      })
      if (!remember) {
        // 正式账号「不记住」仍走 persist；试用账号在 setSession 内已跳过落盘
      }
      const from = authState?.from
      navigate(from && from !== '/login' ? from : '/games', { replace: true })
    } catch (err) {
      toast.error(formatApiError(err, t('errInvalidCredentials'), t))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title={t('login')} subtitle={t('tagline')}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          variant="glass"
          name="email"
          label={t('email')}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          variant="glass"
          name="password"
          label={t('password')}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
        <div className="flex items-center justify-between text-xs text-white/70">
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="accent-white"
            />
            {t('remember')}
          </label>
          <Link to="/forgot-password" className="hover:text-white">
            {t('forgot')}
          </Link>
        </div>
        <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
          {loading ? t('loggingIn') : t('login')}
        </MagneticButton>
        <Button
          type="button"
          variant="secondary"
          className="w-full !rounded-xl"
          onClick={() => void startTrialPreview()}
          disabled={trialLoading || loading}
        >
          {trialLoading ? t('loading') : t('fillTrialPreview')}
        </Button>
        <p className="text-center text-[11px] leading-relaxed text-white/50">{t('fillTrialHint')}</p>
        <p className="text-center text-xs text-white/65">
          {t('noAccount')}{' '}
          <Link to="/register" className="font-medium text-white underline-offset-2 hover:underline">
            {t('register')}
          </Link>
        </p>
        <OAuthButtons className="mt-4 border-t border-white/10 pt-4" />
      </form>
    </AuthShell>
  )
}
