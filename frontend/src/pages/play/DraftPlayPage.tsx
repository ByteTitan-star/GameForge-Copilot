import { Link, Navigate, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { GamePlayer } from '@/components/game/GamePlayer'
import { draftArtifactUrl } from '@/lib/hosting'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'

// 全屏沉浸试玩页：顶部仅一行返回+标题，GamePlayer 撑满剩余高度。
// 高度链路自顶向下：100dvh → flex-col → min-h-0 → flex-1 → stage 撑满。
export function DraftPlayPage() {
  const { gameId, version } = useParams()
  const token = useAuthStore((s) => s.access_token)
  const t = useT()
  if (!token) return <Navigate to="/login" replace />

  const src = draftArtifactUrl(gameId ?? '', version ?? '0')

  return (
    <div className="flex h-[100dvh] flex-col bg-[#0B0F17]">
      <header className="flex flex-none items-center gap-3 px-4 py-2.5 text-white/70">
        <Link
          to="/games"
          className="gf-interactive inline-flex items-center gap-1.5 text-sm text-white/55 transition hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('backToGames')}
        </Link>
        <h1 className="truncate text-sm font-medium text-white/75">
          {t('draftPreviewLabel')
            .replace('{id}', gameId ?? '')
            .replace('{v}', version ?? '')}
        </h1>
      </header>
      <main className="min-h-0 flex-1 px-3 pb-3">
        <GamePlayer
          src={src}
          title={`draft/${gameId}/${version}`}
          variant="stage"
          accessToken={token}
        />
      </main>
    </div>
  )
}
