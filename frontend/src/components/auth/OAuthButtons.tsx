import { oauthEnabled, type OAuthProvider } from '@/lib/oauth'
import { authApi } from '@/api/auth'
import { formatApiError } from '@/api/error-message'
import { useT } from '@/i18n/use-t'
import { useState } from 'react'

type Props = {
  className?: string
}

export function OAuthButtons({ className }: Props) {
  const t = useT()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState<OAuthProvider | null>(null)

  if (!oauthEnabled) return null

  async function start(provider: OAuthProvider) {
    setError('')
    setLoading(provider)
    try {
      const { redirect_url } = await authApi.oauthStart(provider)
      window.location.assign(redirect_url)
    } catch (e) {
      setError(formatApiError(e, t('generationFailed')))
      setLoading(null)
    }
  }

  return (
    <div className={className}>
      <p className="mb-3 text-center text-[11px] uppercase tracking-wider text-white/45">{t('oauthOr')}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <button
          type="button"
          disabled={loading !== null}
          onClick={() => void start('github')}
          className="liquid-glass cursor-pointer rounded-xl border border-white/15 px-4 py-2.5 text-sm font-medium text-white transition hover:border-white/30 disabled:opacity-50"
        >
          {loading === 'github' ? '…' : t('oauthGithub')}
        </button>
        <button
          type="button"
          disabled={loading !== null}
          onClick={() => void start('google')}
          className="liquid-glass cursor-pointer rounded-xl border border-white/15 px-4 py-2.5 text-sm font-medium text-white transition hover:border-white/30 disabled:opacity-50"
        >
          {loading === 'google' ? '…' : t('oauthGoogle')}
        </button>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-center text-sm text-red-300">
          {error}
        </p>
      ) : null}
    </div>
  )
}
