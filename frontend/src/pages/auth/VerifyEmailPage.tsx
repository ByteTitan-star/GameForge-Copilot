import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { AuthShell } from '@/components/auth/AuthShell'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'

export function VerifyEmailPage() {
  const t = useT()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.access_token)
  const patchUser = useAuthStore((s) => s.patchUser)
  const emailFromQuery = params.get('email') ?? ''
  const emailFromState = (location.state as { email?: string } | null)?.email ?? ''
  const initialEmail = emailFromState || emailFromQuery || user?.email || ''
  const [email, setEmail] = useState(initialEmail)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)

  useEffect(() => {
    if (token && user?.email_verified) {
      navigate('/games', { replace: true })
    }
  }, [token, user?.email_verified, navigate])

  useEffect(() => {
    if (initialEmail && !email) setEmail(initialEmail)
  }, [initialEmail, email])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setInfo('')
    setLoading(true)
    try {
      await authApi.verifyEmail(email.trim(), code.trim())
      if (token) {
        patchUser({ email_verified: true })
        navigate('/settings', {
          replace: true,
          state: { justVerified: true, tab: 'llm' as const },
        })
      } else {
        navigate('/login', {
          replace: true,
          state: { email: email.trim(), verified: true },
        })
      }
    } catch (err) {
      setError(formatApiError(err, t('verifyFailed')))
    } finally {
      setLoading(false)
    }
  }

  async function onResend() {
    if (!email.trim()) {
      setError(t('verifyEmailRequired'))
      return
    }
    setError('')
    setInfo('')
    setResending(true)
    try {
      await authApi.resendVerification(email.trim())
      setInfo(t('verifyCodeResent'))
    } catch (err) {
      setError(formatApiError(err, t('verifyResendFailed')))
    } finally {
      setResending(false)
    }
  }

  return (
    <AuthShell
      title={t('verifyTitle')}
      subtitle={
        initialEmail
          ? t('verifySentTo').replace('{email}', initialEmail)
          : t('verifyCodeHint')
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          name="email"
          label={t('email')}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          readOnly={Boolean(token && user?.email)}
        />
        <Input
          name="code"
          label={t('verifyCode')}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          inputMode="numeric"
          pattern="\d{6}"
          maxLength={6}
          placeholder="123456"
          required
          autoFocus
        />
        {error ? (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        ) : null}
        {info ? (
          <p role="status" className="text-sm text-cyan-200/90">
            {info}
          </p>
        ) : null}
        <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading || code.length !== 6}>
          {loading ? t('loading') : t('verifySubmit')}
        </MagneticButton>
        <button
          type="button"
          className="w-full cursor-pointer text-center text-xs text-white/65 underline-offset-2 hover:underline disabled:opacity-50"
          disabled={resending || !email.trim()}
          onClick={() => void onResend()}
        >
          {resending ? t('loading') : t('verifyResend')}
        </button>
        {token ? (
          <p className="text-center text-xs text-white/65">
            <Link to="/games" className="underline-offset-2 hover:underline">
              {t('skipToGames')}
            </Link>
          </p>
        ) : (
          <p className="text-center text-xs text-white/65">
            <Link to="/login" className="underline-offset-2 hover:underline">
              {t('login')}
            </Link>
          </p>
        )}
      </form>
    </AuthShell>
  )
}
