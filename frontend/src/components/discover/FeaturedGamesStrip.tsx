import { useQuery } from '@tanstack/react-query'
import { Loader2, Sparkles } from 'lucide-react'
import { featuredApi } from '@/api/featured'
import { PublicGameCard } from '@/components/games/PublicGameCard'
import { useLocaleStore } from '@/stores/locale-store'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Props = {
  className?: string
  variant?: 'dark' | 'light'
}

export function FeaturedGamesStrip({ className, variant = 'dark' }: Props) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const q = useQuery({
    queryKey: ['featured-games', locale],
    queryFn: () => featuredApi.list(locale),
  })

  const games = q.data ?? []
  if (!q.isLoading && games.length === 0) return null

  const dark = variant === 'dark'

  return (
    <section className={cn('space-y-4', className)}>
      <div>
        <p
          className={cn(
            'flex items-center gap-2 font-mono text-xs font-semibold tracking-[0.14em] uppercase',
            dark ? 'text-white/70' : 'gf-text-accent',
          )}
        >
          <Sparkles className="h-3.5 w-3.5" />
          {t('featuredBadge')}
        </p>
        <h2
          className={cn(
            'mt-1.5 text-2xl font-semibold tracking-tight sm:text-[26px]',
            dark ? 'text-white' : 'gf-page-body',
          )}
        >
          {t('featuredTitle')}
        </h2>
        <p className={cn('mt-1.5 text-sm', dark ? 'text-white/65' : 'gf-page-muted')}>
          {t('featuredSubtitle')}
        </p>
      </div>

      {q.isLoading ? (
        <p className={cn('flex items-center gap-2 text-sm', dark ? 'text-white/50' : 'gf-page-muted')}>
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('loading')}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {games.map((g) => (
            <PublicGameCard
              key={g.game_id}
              game={g}
              compact
              variant={variant === 'light' ? 'theme' : 'dark'}
            />
          ))}
        </div>
      )}
    </section>
  )
}
