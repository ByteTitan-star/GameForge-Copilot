import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { AuthShell } from '@/components/auth/AuthShell'
import { OAuthButtons } from '@/components/auth/OAuthButtons'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'
import { toast } from '@/stores/toast-store'

export function RegisterPage() {
  const t = useT()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (password !== confirm) {
      toast.error(t('errPasswordMismatch'))
      return
    }
    setLoading(true)
    try {
      const trimmedEmail = email.trim()
      await authApi.register(trimmedEmail, password)
      // 注册成功 → 跳验证页输码；password 仅存内存 route state，用于验证后自动登录
      navigate('/verify-email', {
        replace: true,
        state: { email: trimmedEmail, password },
      })
    } catch (err) {
      toast.error(formatApiError(err, t('errRegisterFailed')))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title={t('register')} subtitle={t('registerSubtitle')}>
      <form className="space-y-4" onSubmit={onSubmit} autoComplete="off">
        <Input
          variant="glass"
          name="email"
          label={t('email')}
          type="email"
          autoComplete="off"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          variant="glass"
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
          variant="glass"
          name="confirm"
          label={t('confirmPassword')}
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          minLength={8}
        />
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
