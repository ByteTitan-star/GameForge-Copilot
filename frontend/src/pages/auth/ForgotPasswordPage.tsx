import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { AuthShell } from '@/components/auth/AuthShell'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/Input'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'

type Step = 'request' | 'sent' | 'confirm' | 'done'

export function ForgotPasswordPage() {
  const t = useT()
  const navigate = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const [params] = useSearchParams()
  const tokenFromLink = params.get('token') ?? ''
  const [step, setStep] = useState<Step>(tokenFromLink ? 'confirm' : 'request')
  const [email, setEmail] = useState('')
  const [token, setToken] = useState(tokenFromLink)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onRequest(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.requestPasswordReset(email.trim())
      setStep('sent')
    } catch (err) {
      setError(formatApiError(err, t('errRequestFailed')))
    } finally {
      setLoading(false)
    }
  }

  async function onConfirm(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await authApi.confirmPasswordReset(token.trim(), password)
      const loginEmail = result.email || email.trim()
      if (loginEmail) {
        const session = await authApi.login(loginEmail, password)
        setSession({
          user: session.user,
          access_token: session.access_token,
          refresh_token: session.refresh_token,
        })
        navigate('/games', { replace: true, state: { passwordReset: true } })
        return
      }
      setStep('done')
    } catch (err) {
      setError(formatApiError(err, t('errResetFailed')))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title={t('forgotTitle')} subtitle={t('forgotHint')}>
      {step === 'done' ? (
        <div className="space-y-4 text-sm text-white/80">
          <p role="status">{t('resetDoneManualLogin')}</p>
          <Link to="/login" className="inline-block text-white underline-offset-2 hover:underline">
            {t('login')}
          </Link>
        </div>
      ) : null}

      {step === 'sent' ? (
        <div className="space-y-4 text-sm text-white/80">
          <p role="status">{t('resetEmailSent')}</p>
          <button
            type="button"
            className="cursor-pointer text-xs text-white/65 underline-offset-2 hover:underline"
            onClick={() => setStep('confirm')}
          >
            {t('resetEnterToken')}
          </button>
          <p className="text-center text-xs text-white/65">
            <Link to="/login" className="underline-offset-2 hover:underline">
              {t('login')}
            </Link>
          </p>
        </div>
      ) : null}

      {step === 'request' ? (
        <form className="space-y-4" onSubmit={onRequest}>
          <Input
            name="email"
            label={t('email')}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          {error ? (
            <p role="alert" className="text-sm text-red-300">
              {error}
            </p>
          ) : null}
          <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
            {t('sendReset')}
          </MagneticButton>
          <p className="text-center text-xs text-white/65">
            <Link to="/login" className="underline-offset-2 hover:underline">
              {t('login')}
            </Link>
          </p>
        </form>
      ) : null}

      {step === 'confirm' ? (
        <form className="space-y-4" onSubmit={onConfirm}>
          {tokenFromLink ? (
            <p className="text-xs text-white/55">{t('resetLinkReady')}</p>
          ) : (
            <p className="text-xs text-white/55">{t('resetTokenHint')}</p>
          )}
          {!tokenFromLink ? (
            <Input
              name="token"
              label={t('resetToken')}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
            />
          ) : null}
          <Input
            name="password"
            label={t('newPassword')}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            autoFocus={Boolean(tokenFromLink)}
          />
          {error ? (
            <p role="alert" className="text-sm text-red-300">
              {error}
            </p>
          ) : null}
          <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
            {loading ? t('loading') : t('resetConfirm')}
          </MagneticButton>
        </form>
      ) : null}
    </AuthShell>
  )
}
