import { Navigate, useParams } from 'react-router-dom'
import { GamePlayer } from '@/components/game/GamePlayer'
import { draftArtifactUrl } from '@/lib/hosting'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'

export function DraftPlayPage() {
  const { gameId, version } = useParams()
  const token = useAuthStore((s) => s.access_token)
  const t = useT()
  if (!token) return <Navigate to="/login" replace />

  const src = draftArtifactUrl(gameId ?? '', version ?? '0')

  return (
    <div className="min-h-screen bg-[#f0f0f0] px-4 py-8 md:px-8">
      <div className="mx-auto max-w-5xl space-y-4">
        <h1 className="text-xl text-[rgba(30,50,90,0.9)]">
          {t('draftPreviewLabel').replace('{id}', gameId ?? '').replace('{v}', version ?? '')}
        </h1>
        <GamePlayer
          src={src}
          title={`draft/${gameId}/${version}`}
          accessToken={token}
        />
      </div>
    </div>
  )
}
