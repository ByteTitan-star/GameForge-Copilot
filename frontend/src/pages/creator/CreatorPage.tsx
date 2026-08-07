import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { creatorApi } from '@/api/creator'
import { PublicGameCard } from '@/components/games/PublicGameCard'
import { useT } from '@/i18n/use-t'

export function CreatorPage() {
  const t = useT()
  const { handle = '' } = useParams()

  const q = useQuery({
    queryKey: ['creator', handle],
    enabled: Boolean(handle),
    queryFn: () => creatorApi.get(handle),
  })

  const profile = q.data

  if (q.isLoading) {
    return (
      <div className="grid min-h-[50vh] place-items-center text-white/60">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="mx-auto max-w-lg px-6 py-20 text-center text-white">
        <h1 className="text-2xl font-medium">{t('creatorNotFound')}</h1>
        <Link to="/discover" className="mt-4 inline-block text-sm text-cyan-200 hover:underline">
          {t('discover')}
        </Link>
      </div>
    )
  }

  return (
    <div className="relative min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
        <Link to="/discover" className="inline-flex items-center gap-1.5 text-sm text-white/55 hover:text-white">
          <ArrowLeft className="h-4 w-4" />
          {t('discover')}
        </Link>
        <header className="mt-6 border-b border-white/10 pb-6">
          <p className="font-mono text-[11px] tracking-[0.14em] text-cyan-300/70 uppercase">
            @{profile.handle}
          </p>
          <h1 className="mt-2 text-3xl font-normal tracking-tight">{profile.display_name}</h1>
          <div className="mt-3 flex flex-wrap gap-4 text-sm text-white/50">
            <span>{t('creatorTotalPlays').replace('{n}', String(profile.total_plays))}</span>
            {profile.latest_published_at ? (
              <span>
                {t('creatorLatest')}: {new Date(profile.latest_published_at).toLocaleDateString()}
              </span>
            ) : null}
          </div>
        </header>

        <section className="mt-8">
          <h2 className="text-lg font-medium">{t('creatorGames')}</h2>
          {profile.games.length === 0 ? (
            <p className="mt-4 text-sm text-white/50">{t('creatorEmpty')}</p>
          ) : (
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {profile.games.map((g) => (
                <PublicGameCard
                  key={g.game_id}
                  game={{
                    game_id: g.game_id,
                    title: g.title,
                    slug: g.slug,
                    play_count: g.play_count,
                    published_at: g.published_at,
                    author_display: profile.display_name,
                    creator: { handle: profile.handle, display_name: profile.display_name },
                  }}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
