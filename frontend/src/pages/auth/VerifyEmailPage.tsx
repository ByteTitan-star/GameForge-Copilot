import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { isApiError } from '@/api/errors'
import { AuthShell } from '@/components/auth/AuthShell'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'

export function VerifyEmailPage() {
  const t = useT()
  const navigate = useNavigate()
  const location = useLocation()
  const emailFromState = (location.state as { email?: string } | null)?.email
  const patchUser = useAuthStore((s) => s.patchUser)
  const [token, setToken] = useState('123456')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.verifyEmail(token.trim())
      patchUser({ email_verified: true })
      navigate('/login', { replace: true })
    } catch (err) {
      setError(isApiError(err) ? err.message : '验证失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title={t('verifyTitle')}
      subtitle={emailFromState ? `已发送至 ${emailFromState}` : t('verifyHint')}
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          name="token"
          label={t('verifyCode')}
          value={token}
          onChange={(e) => setToken(e.target.value)}
          required
        />
        <p className="text-xs text-white/55">{t('verifyHint')}</p>
        {error ? (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        ) : null}
        <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
          {t('verifySubmit')}
        </MagneticButton>
        <p className="text-center text-xs text-white/65">
          <Link to="/login" className="underline-offset-2 hover:underline">
            {t('login')}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
