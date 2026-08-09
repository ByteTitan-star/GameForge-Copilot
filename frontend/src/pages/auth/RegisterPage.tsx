import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { AuthShell } from '@/components/auth/AuthShell'
import { OAuthButtons } from '@/components/auth/OAuthButtons'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/Input'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'

export function RegisterPage() {
  const t = useT()
  const navigate = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError(t('errPasswordMismatch'))
      return
    }
    setLoading(true)
    try {
      const trimmedEmail = email.trim()
      await authApi.register(trimmedEmail, password)
      const session = await authApi.login(trimmedEmail, password)
      setSession({
        user: session.user,
        access_token: session.access_token,
        refresh_token: session.refresh_token,
      })
      navigate('/games', { replace: true })
    } catch (err) {
      setError(formatApiError(err, t('errRegisterFailed')))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title={t('register')} subtitle={t('registerSubtitle')}>
      <form className="space-y-4" onSubmit={onSubmit} autoComplete="off">
        <Input
          name="email"
          label={t('email')}
          type="email"
          autoComplete="off"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          name="password"
          label={t('password')}
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
        <Input
          name="confirm"
          label={t('confirmPassword')}
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          minLength={8}
        />
        {error ? (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        ) : null}
        <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
          {loading ? t('registering') : t('register')}
        </MagneticButton>
        <p className="text-center text-xs text-white/65">
          {t('hasAccount')}{' '}
          <Link to="/login" className="font-medium text-white underline-offset-2 hover:underline">
            {t('login')}
          </Link>
        </p>
        <OAuthButtons className="mt-4 border-t border-white/10 pt-4" />
      </form>
    </AuthShell>
  )
}
