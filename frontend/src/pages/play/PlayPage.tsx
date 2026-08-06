import { useParams } from 'react-router-dom'
import { GamePlayer } from '@/components/game/GamePlayer'

/** 公开试玩：产物 URL 后续由托管服务提供；mock 用占位页 */
export function PlayPage() {
  const { slug } = useParams()
  const src = `/mock-play.html?slug=${encodeURIComponent(slug ?? '')}`

  return (
    <div className="min-h-screen bg-[#f0f0f0] px-4 py-8 md:px-8">
      <div className="mx-auto max-w-5xl space-y-4">
        <h1 className="text-xl text-[rgba(30,50,90,0.9)]">试玩 · {slug}</h1>
        <GamePlayer src={src} title={`play/${slug}`} />
      </div>
    </div>
  )
}
