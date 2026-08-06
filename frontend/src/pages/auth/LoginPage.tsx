import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { isApiError } from '@/api/errors'
import { AuthShell } from '@/components/auth/AuthShell'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'

export function LoginPage() {
  const t = useT()
  const navigate = useNavigate()
  const location = useLocation()
  const setSession = useAuthStore((s) => s.setSession)
  const [email, setEmail] = useState('demo@gameforge.dev')
  const [password, setPassword] = useState('password123')
  const [remember, setRemember] = useState(true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await authApi.login(email.trim(), password)
      setSession({
        user: data.user,
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      })
      if (!remember) {
        // 仍写入 persist；后续可拆 ephemeral session
      }
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from !== '/login' ? from : '/games', { replace: true })
    } catch (err) {
      setError(isApiError(err) ? err.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title={t('login')} subtitle={t('tagline')}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          name="email"
          label={t('email')}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          name="password"
          label={t('password')}
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
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
        {error ? (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        ) : null}
        <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
          {loading ? t('loggingIn') : t('login')}
        </MagneticButton>
        <p className="text-center text-xs text-white/65">
          {t('noAccount')}{' '}
          <Link to="/register" className="font-medium text-white underline-offset-2 hover:underline">
            {t('register')}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
