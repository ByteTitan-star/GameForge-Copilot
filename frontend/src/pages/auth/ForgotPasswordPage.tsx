import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { isApiError } from '@/api/errors'
import { AuthShell } from '@/components/auth/AuthShell'
import { MagneticButton } from '@/components/ui/magnetic-button'
import { Input } from '@/components/ui/input'
import { useT } from '@/i18n/use-t'

export function ForgotPasswordPage() {
  const t = useT()
  const [step, setStep] = useState<'request' | 'confirm' | 'done'>('request')
  const [email, setEmail] = useState('')
  const [token, setToken] = useState('654321')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onRequest(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.requestPasswordReset(email.trim())
      setStep('confirm')
    } catch (err) {
      setError(isApiError(err) ? err.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  async function onConfirm(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.confirmPasswordReset(token.trim(), password)
      setStep('done')
    } catch (err) {
      setError(isApiError(err) ? err.message : '重置失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title={t('forgotTitle')} subtitle={t('forgotHint')}>
      {step === 'done' ? (
        <div className="space-y-4 text-sm text-white/80">
          <p role="status">密码已重置，请登录。</p>
          <Link to="/login" className="inline-block text-white underline-offset-2 hover:underline">
            {t('login')}
          </Link>
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
          <p className="text-xs text-white/55">Mock：邮件不会真正发送。使用重置码 654321 继续。</p>
          <Input
            name="token"
            label="重置码"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
          />
          <Input
            name="password"
            label="新密码"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />
          {error ? (
            <p role="alert" className="text-sm text-red-300">
              {error}
            </p>
          ) : null}
          <MagneticButton type="submit" className="w-full !rounded-xl" disabled={loading}>
            确认重置
          </MagneticButton>
        </form>
      ) : null}
    </AuthShell>
  )
}
