import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { AuthShell } from '@/components/auth/AuthShell'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { toast } from '@/stores/toast-store'

const RESEND_COOLDOWN = 60

export function VerifyEmailPage() {
  const t = useT()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const setSession = useAuthStore((s) => s.setSession)

  const routeState = (location.state ?? {}) as { email?: string; password?: string }
  const initialEmail = routeState.email ?? params.get('email') ?? ''

  const [email, setEmail] = useState(initialEmail)
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN)

  // 进入页面即倒计时：注册时已发过一次码，避免立刻重复请求
  useEffect(() => {
    if (cooldown <= 0) return
    const id = window.setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => window.clearTimeout(id)
  }, [cooldown])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      toast.error(t('errVerifyEmailMissing'))
      return
    }
    setLoading(true)
    try {
      await authApi.verifyEmail(trimmedEmail, code.trim())
      // 注册跳转带来 password：验证后直接自动登录；邮件链接进入则回登录页
      if (routeState.password) {
        const session = await authApi.login(trimmedEmail, routeState.password)
        setSession({
          user: session.user,
          access_token: session.access_token,
          refresh_token: session.refresh_token,
        })
        navigate('/games', { replace: true })
      } else {
        navigate('/login', { replace: true, state: { email: trimmedEmail } })
      }
    } catch (err) {
      toast.error(formatApiError(err, t('errVerifyCode')))
    } finally {
      setLoading(false)
    }
  }

  async function onResend() {
    const trimmedEmail = email.trim()
    if (!trimmedEmail || cooldown > 0) return
    try {
      await authApi.resendVerification(trimmedEmail)
      toast.success(t('verifyCodeResent'))
      setCooldown(RESEND_COOLDOWN)
    } catch (err) {
      toast.error(formatApiError(err, t('errVerifyCode')))
    }
  }

  return (
    <AuthShell title={t('verifyEmailTitle')} subtitle={t('verifyEmailSubtitle')}>
      <form className="space-y-4" onSubmit={onSubmit} autoComplete="off">
        <Input
          variant="glass"
          name="email"
          label={t('email')}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          variant="glass"
          name="code"
          label={t('verifyCodeLabel')}
          inputMode="numeric"
          placeholder={t('verifyCodePlaceholder')}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          required
        />
        <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
          {loading ? t('verifying') : t('verifySubmit')}
        </MagneticButton>
        <button
          type="button"
          onClick={onResend}
          disabled={cooldown > 0 || loading}
          className="w-full cursor-pointer text-center text-xs text-white/65 underline-offset-2 hover:underline disabled:cursor-default disabled:opacity-50 disabled:no-underline"
        >
          {cooldown > 0 ? `${t('resendCode')} (${cooldown}s)` : t('resendCode')}
        </button>
        <p className="text-center text-xs text-white/65">
          <Link to="/login" className="underline-offset-2 hover:underline">
            {t('login')}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
