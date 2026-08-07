import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { AuthShell } from '@/components/auth/AuthShell'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'

export function RegisterPage() {
  const t = useT()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('两次密码不一致')
      return
    }
    setLoading(true)
    try {
      await authApi.register(email.trim(), password)
      navigate('/verify-email', { state: { email: email.trim() } })
    } catch (err) {
      setError(formatApiError(err, '注册失败'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title={t('register')} subtitle="注册后请验证邮箱，再配置 LLM 开始生成">
      <form className="space-y-4" onSubmit={onSubmit}>
        <Input
          name="email"
          label={t('email')}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          name="password"
          label={t('password')}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
        />
        <Input
          name="confirm"
          label={t('confirmPassword')}
          type="password"
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
      </form>
    </AuthShell>
  )
}
