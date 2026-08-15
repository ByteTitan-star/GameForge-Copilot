import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, GitFork, Loader2, Sparkles } from 'lucide-react'
import { officialApi } from '@/api/official'
import { formatApiError } from '@/api/error-message'
import { useT } from '@/i18n/use-t'
import { useLocaleStore } from '@/stores/locale-store'
import { cn } from '@/lib/cn'
import { CreatorLink } from '@/components/creator/CreatorLink'

type Props = {
  accessToken?: string | null
  trial?: boolean
  onToast?: (msg: string) => void
  className?: string
  compact?: boolean
}

export function OfficialGameCards({
  accessToken,
  trial = false,
  onToast,
  className,
  compact = false,
}: Props) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const navigate = useNavigate()
  const [forking, setForking] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['official-games', locale],
    queryFn: () => officialApi.list(locale),
  })

  async function fork(slug: string) {
    if (!accessToken) {
      navigate('/login')
      return
    }
    setForking(slug)
    try {
      const created = await officialApi.fork(slug, accessToken)
      onToast?.(t('officialForkOk'))
      navigate(`/forge/${created.game_id}`)
    } catch (e) {
      onToast?.(formatApiError(e, t('officialForkFailed')))
    } finally {
      setForking(null)
    }
  }

  if (q.isLoading) {
    return (
      <p className={cn('flex items-center gap-2 text-sm text-white/50', className)}>
        <Loader2 className="h-4 w-4 animate-spin" />
        {t('loading')}
      </p>
    )
  }

  const games = q.data ?? []

  return (
    <section className={cn('space-y-4', className)}>
      <div>
        <p className="font-mono text-[10px] tracking-[0.14em] uppercase text-white/45">
          {t('officialGamesBadge')}
        </p>
        <h2 className={cn('font-medium tracking-tight', compact ? 'text-lg' : 'text-xl md:text-2xl')}>
          {t('officialGamesTitle')}
        </h2>
        <p className="mt-1 text-sm text-white/55">{t('officialGamesSubtitle')}</p>
      </div>

      <div className={cn('grid gap-3', compact ? 'sm:grid-cols-1' : 'sm:grid-cols-2 lg:grid-cols-3')}>
        {games.map((g) => (
          <article
            key={g.slug}
            className="rounded-2xl border border-white/12 bg-black/35 p-4 backdrop-blur-md"
          >
            <h3 className="text-base font-medium">{g.title}</h3>
            <CreatorLink official className="mt-1 block text-white/50" />
            <p className="mt-1.5 text-xs leading-relaxed text-white/55">{g.description}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                to={`/play/${g.slug}`}
                className="inline-flex items-center gap-1 rounded-lg bg-white/90 px-2.5 py-1.5 text-xs font-medium text-black transition hover:bg-white"
              >
                {t('officialPlay')}
                <ExternalLink className="h-3 w-3" />
              </Link>
              {accessToken && !trial ? (
                <button
                  type="button"
                  disabled={forking === g.slug}
                  onClick={() => void fork(g.slug)}
                  className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-white/20 px-2.5 py-1.5 text-xs text-white/85 transition hover:border-white/40 disabled:opacity-50"
                >
                  {forking === g.slug ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <GitFork className="h-3 w-3" />
                  )}
                  {t('officialFork')}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>

      <Link
        to="/forge"
        className="inline-flex items-center gap-1.5 text-sm text-cyan-200/90 transition hover:text-cyan-100"
      >
        <Sparkles className="h-4 w-4" />
        {t('officialBlankCreate')}
      </Link>
    </section>
  )
}
