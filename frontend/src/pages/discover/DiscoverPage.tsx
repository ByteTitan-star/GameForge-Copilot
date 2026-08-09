import { useQuery } from '@tanstack/react-query'
import { Compass, Loader2 } from 'lucide-react'
import { publicGamesApi } from '@/api/public-games'
import { FeaturedGamesStrip } from '@/components/discover/FeaturedGamesStrip'
import { PublicGameCard } from '@/components/games/PublicGameCard'
import { useT } from '@/i18n/use-t'

export function DiscoverPage() {
  const t = useT()
  const query = useQuery({
    queryKey: ['public-games'],
    queryFn: () => publicGamesApi.list(),
  })

  const games = query.data ?? []

  return (
    <div className="relative min-h-full bg-[#0a0a0a] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,rgba(34,211,238,0.08),transparent_55%),radial-gradient(ellipse_at_bottom,rgba(168,85,247,0.06),transparent_50%)]" />

      <div className="relative z-10 mx-auto max-w-6xl px-5 py-8 sm:px-8 md:py-12">
        <header className="mb-10 flex flex-wrap items-end justify-between gap-4 border-b border-white/10 pb-6">
          <div>
            <p className="flex items-center gap-2 font-mono text-[11px] tracking-[0.16em] text-cyan-300/70 uppercase">
              <Compass className="h-3.5 w-3.5" />
              {t('discoverBadge')}
            </p>
            <h1 className="mt-2 text-3xl font-normal tracking-tight sm:text-4xl">{t('discoverTitle')}</h1>
            <p className="mt-2 max-w-xl text-sm text-white/60">{t('discoverSubtitle')}</p>
          </div>
        </header>

        <FeaturedGamesStrip variant="dark" className="mb-10" />

        {query.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-white/60">
            <Loader2 className="h-4 w-4 animate-spin" />
            {t('loading')}
          </div>
        ) : null}

        {query.isError ? (
          <p role="alert" className="text-sm text-rose-300">
            {t('loadFailed')}
          </p>
        ) : null}

        {!query.isLoading && games.length === 0 ? (
          <p className="text-sm text-white/55">{t('discoverEmpty')}</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {games.map((g) => (
              <PublicGameCard key={g.game_id} game={g} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
