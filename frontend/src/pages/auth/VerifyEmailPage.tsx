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
  const emailFromState = (location.state as { email?: string } | null)?.email
  const tokenFromLink = params.get('token') ?? ''
  const patchUser = useAuthStore((s) => s.patchUser)
  const [token, setToken] = useState(tokenFromLink)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [autoTried, setAutoTried] = useState(false)

  async function verify(value: string) {
    setError('')
    setLoading(true)
    try {
      await authApi.verifyEmail(value.trim())
      patchUser({ email_verified: true })
      navigate('/settings', { replace: true, state: { justVerified: true } })
    } catch (err) {
      setError(formatApiError(err, '验证失败'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!tokenFromLink || autoTried) return
    setAutoTried(true)
    void verify(tokenFromLink)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenFromLink, autoTried])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    await verify(token)
  }

  return (
    <AuthShell
      title={t('verifyTitle')}
      subtitle={
        emailFromState
          ? `验证邮件已发送至 ${emailFromState}；本地开发请到 Worker 终端查看 [dev-email] 链接。`
          : '请输入邮件中的验证令牌；若从邮件链接进入将自动提交。'
      }
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          name="token"
          label={t('verifyCode')}
          value={token}
          onChange={(e) => setToken(e.target.value)}
          required
        />
        {error ? (
          <p role="alert" className="text-sm text-red-300">
            {error}
          </p>
        ) : null}
        <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
          {loading ? '…' : t('verifySubmit')}
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
