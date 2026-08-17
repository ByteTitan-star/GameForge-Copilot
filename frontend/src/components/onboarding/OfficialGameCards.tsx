import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, GitFork, Loader2, Plus, Sparkles } from 'lucide-react'
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
    <section className={cn('space-y-5', className)}>
      <div>
        <p className="font-mono text-xs font-semibold tracking-[0.14em] text-white/70 uppercase">
          {t('officialGamesBadge')}
        </p>
        <h2
          className={cn(
            'font-semibold tracking-tight text-white',
            compact ? 'text-lg' : 'text-2xl md:text-[26px]',
          )}
        >
          {t('officialGamesTitle')}
        </h2>
        <p className="mt-1.5 text-sm text-white/65">{t('officialGamesSubtitle')}</p>
      </div>

      <div className={cn('grid gap-4', compact ? 'sm:grid-cols-1' : 'sm:grid-cols-2 xl:grid-cols-4')}>
        {games.map((g) => (
          <article
            key={g.slug}
            className="flex min-h-[168px] flex-col rounded-2xl border border-white/10 bg-[#1a1d21] p-4 transition-colors duration-300 hover:border-white/25"
          >
            <h3 className="text-base font-medium text-white">{g.title}</h3>
            <CreatorLink official className="mt-1 block text-white/55" />
            <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-white/65">
              {g.description}
            </p>
            <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
              <Link
                to={`/play/${g.slug}`}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-white/20 px-3.5 text-sm font-medium text-white/90 transition hover:border-white/40 hover:bg-white/10"
              >
                {t('officialPlay')}
                <ExternalLink className="h-3.5 w-3.5" />
              </Link>
              {accessToken && !trial ? (
                <button
                  type="button"
                  disabled={forking === g.slug}
                  onClick={() => void fork(g.slug)}
                  className="gf-interactive inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg bg-white/90 px-3.5 text-sm font-semibold text-black transition hover:bg-white disabled:opacity-50"
                >
                  {forking === g.slug ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <GitFork className="h-3.5 w-3.5" />
                  )}
                  {t('officialFork')}
                </button>
              ) : null}
            </div>
          </article>
        ))}

        {/* 从空白开始：与模板卡同规格的第四张入口卡——权重降一级（更弱底色 + 小图标），
            表现为「第四种开始方式」而非更大的 CTA */}
        <Link
          to="/forge"
          className={cn(
            'gf-interactive group flex min-h-[168px] cursor-pointer flex-col items-start rounded-2xl',
            'border border-dashed border-white/15 bg-white/[0.02] p-4',
            'transition-colors duration-300 hover:border-white/35 hover:bg-white/[0.06]',
            compact && 'sm:grid-cols-1',
          )}
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-white/70 transition-colors duration-300 group-hover:text-white">
            <Plus className="h-4 w-4" />
          </span>
          <h3 className="mt-3 text-[15px] font-medium text-white/85">{t('officialBlankCreate')}</h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-white/55">
            {t('officialBlankCreateHint')}
          </p>
          <span className="mt-auto inline-flex items-center gap-1.5 pt-4 text-sm text-white/60 transition-colors group-hover:text-white/90">
            <Sparkles className="h-3.5 w-3.5" />
            {t('startForge')}
          </span>
        </Link>
      </div>
    </section>
  )
}
