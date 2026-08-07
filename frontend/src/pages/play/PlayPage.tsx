import { useParams } from 'react-router-dom'
import { GamePlayer } from '@/components/game/GamePlayer'
import { playArtifactUrl } from '@/lib/hosting'

/** 公开试玩：iframe sandbox 挂载托管产物 */
export function PlayPage() {
  const { slug } = useParams()
  const src = playArtifactUrl(slug ?? '')

  return (
    <div className="min-h-screen bg-[#f0f0f0] px-4 py-8 md:px-8">
      <div className="mx-auto max-w-5xl space-y-4">
        <h1 className="text-xl text-[rgba(30,50,90,0.9)]">试玩 · {slug}</h1>
        <GamePlayer src={src} title={`play/${slug}`} />
      </div>
    </div>
  )
}
