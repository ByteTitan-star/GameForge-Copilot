import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Role } from '@/api/enums'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'

/** OAuth 回调：query 携带 token；后端也可 redirect 到 /login?token= */
export function OAuthCallbackPage() {
  const t = useT()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const setSession = useAuthStore((s) => s.setSession)

  useEffect(() => {
    const accessToken = params.get('access_token') ?? params.get('token')
    const refreshToken = params.get('refresh_token') ?? ''
    const email = params.get('email')
    const userId = params.get('user_id')

    if (accessToken && email && userId) {
      setSession({
        user: {
          user_id: userId,
          email,
          email_verified: params.get('email_verified') !== 'false',
          role: params.get('role') === 'admin' ? Role.admin : Role.user,
        },
        access_token: accessToken,
        refresh_token: refreshToken,
      })
      navigate('/games', { replace: true })
      return
    }

    navigate('/login', { replace: true })
  }, [navigate, params, setSession])

  return (
    <div className="grid min-h-screen place-items-center bg-black text-white">
      <p className="text-sm text-white/60">{t('loading')}</p>
    </div>
  )
}
