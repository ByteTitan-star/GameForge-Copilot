import { useMemo, useState, type ComponentType, type CSSProperties } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight, Compass, Flame, Gamepad2, RefreshCw, Search, Sparkles } from 'lucide-react'
import { publicGamesApi } from '@/api/public-games'
import { FeaturedGamesStrip } from '@/components/discover/FeaturedGamesStrip'
import { PublicGameCard } from '@/components/games/PublicGameCard'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { useLocaleStore } from '@/stores/locale-store'
import { cn } from '@/lib/cn'

type SortKey = 'latest' | 'popular'
type LucideIcon = ComponentType<{ className?: string }>

/** 骨架灰块：跟随 --gf-text 的低透明度，浅/深主题都成立。 */
const skeletonStyle: CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--gf-text) 8%, transparent)',
}

/** 紧凑数字：≥1000 走 1.2k / 12k，否则原样。 */
function formatStat(n: number): string {
  if (n >= 10000) return `${Math.round(n / 1000)}k`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

function StatCell({
  icon: Icon,
  value,
  label,
  loading,
}: {
  icon: LucideIcon
  value: string
  label: string
  loading: boolean
}) {
  return (
    <div className="flex items-center gap-2.5">
      <Icon className="gf-text-accent h-4 w-4 shrink-0" />
      <div className="min-w-[2.5rem]">
        {loading ? (
          <div className="h-6 w-12 animate-pulse rounded" style={skeletonStyle} />
        ) : (
          <p className="font-mono text-xl leading-none text-[var(--gf-text)] tabular-nums">{value}</p>
        )}
        <p className="gf-page-muted mt-1 text-[11px] font-medium uppercase tracking-wider">{label}</p>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="gf-glass overflow-hidden rounded-2xl">
      <div className="aspect-[16/10] w-full min-h-[160px] animate-pulse" style={skeletonStyle} />
      <div className="space-y-3 p-4">
        <div className="h-5 w-3/4 animate-pulse rounded" style={skeletonStyle} />
        <div className="h-3 w-1/2 animate-pulse rounded" style={skeletonStyle} />
        <div className="h-8 w-24 animate-pulse rounded-lg" style={skeletonStyle} />
      </div>
    </div>
  )
}

export function DiscoverPage() {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const token = useAuthStore((s) => s.access_token)
  const query = useQuery({
    queryKey: ['public-games', locale],
    queryFn: () => publicGamesApi.list(locale),
  })

  const games = query.data ?? []
  const [q, setQ] = useState('')
  const [sort, setSort] = useState<SortKey>('latest')
  const [featuredOnly, setFeaturedOnly] = useState(false)

  const stats = useMemo(() => {
    const total = games.reduce((s, g) => s + g.play_count, 0)
    const weekAgo = Date.now() - 7 * 86_400_000
    const fresh = games.filter((g) => Date.parse(g.published_at ?? '') > weekAgo).length
    return { count: games.length, total, fresh }
  }, [games])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const list = games.filter((g) => {
      if (featuredOnly && !g.featured) return false
      if (needle && !g.title.toLowerCase().includes(needle)) return false
      return true
    })
    list.sort((a, b) =>
      sort === 'popular'
        ? b.play_count - a.play_count
        : Date.parse(b.published_at ?? '') - Date.parse(a.published_at ?? ''),
    )
    return list
  }, [games, q, featuredOnly, sort])

  const clearFilters = () => {
    setQ('')
    setFeaturedOnly(false)
  }

  const hasFilters = q.trim() !== '' || featuredOnly

  return (
    <div className="relative min-h-full bg-[var(--gf-bg)] text-[var(--gf-text)]">
      {/* 氛围光斑：复用 .gf-theme-orb-*，跟随 --gf-primary/secondary + glow 强度，主题驱动 */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden>
        <div className="gf-theme-orb gf-theme-orb-a" />
        <div className="gf-theme-orb gf-theme-orb-b" />
        <div className="gf-theme-orb gf-theme-orb-c" />
      </div>

      <div className="relative z-10 mx-auto max-w-6xl px-5 py-8 sm:px-8 md:py-12">
        <header className="mb-10 border-b border-[var(--gf-border)] pb-6">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <p className="gf-text-accent flex items-center gap-2 text-[11px] font-medium tracking-[0.14em] uppercase">
                <Compass className="h-3.5 w-3.5" />
                {t('discoverBadge')}
              </p>
              <h1 className="gf-font-display mt-2 bg-[linear-gradient(var(--gf-gradient-angle),var(--gf-secondary),var(--gf-primary))] bg-clip-text text-4xl font-semibold tracking-tight text-transparent sm:text-5xl">
                {t('discoverTitle')}
              </h1>
              <p className="gf-page-subtitle mt-3 max-w-xl">{t('discoverSubtitle')}</p>
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
              <StatCell
                icon={Gamepad2}
                value={formatStat(stats.count)}
                label={t('discoverStatGames')}
                loading={query.isLoading}
              />
              <StatCell
                icon={Flame}
                value={formatStat(stats.total)}
                label={t('discoverStatPlays')}
                loading={query.isLoading}
              />
              <StatCell
                icon={Sparkles}
                value={formatStat(stats.fresh)}
                label={t('discoverStatNew')}
                loading={query.isLoading}
              />
            </div>
          </div>
        </header>

        <FeaturedGamesStrip variant="light" className="mb-10" />

        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <label className="relative block w-full sm:w-72">
            <Search className="gf-page-muted pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t('discoverSearchPh')}
              aria-label={t('discoverSearchPh')}
              className="gf-input h-11 w-full rounded-xl pr-3 pl-9 text-sm"
            />
          </label>

          <div className="flex flex-wrap items-center gap-2">
            <div
              role="radiogroup"
              aria-label={t('discoverSortPopular')}
              className="flex items-center gap-1 rounded-xl border border-[var(--gf-border)] bg-[var(--gf-surface)] p-1"
            >
              {(['latest', 'popular'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  role="radio"
                  aria-checked={sort === s}
                  onClick={() => setSort(s)}
                  className={cn(
                    'gf-interactive cursor-pointer rounded-lg px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition',
                    sort === s ? 'gf-filter-active' : 'gf-page-muted hover:text-[var(--gf-text)]',
                  )}
                >
                  {t(s === 'latest' ? 'discoverSortLatest' : 'discoverSortPopular')}
                </button>
              ))}
            </div>

            <button
              type="button"
              aria-pressed={featuredOnly}
              onClick={() => setFeaturedOnly((v) => !v)}
              className={cn(
                'gf-interactive inline-flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-2 font-mono text-[11px] uppercase tracking-wider transition',
                featuredOnly
                  ? 'gf-border-accent gf-bg-accent-soft gf-text-accent'
                  : 'gf-chip hover:text-[var(--gf-text)]',
              )}
            >
              <Sparkles className="h-3.5 w-3.5" />
              {t('discoverFilterFeatured')}
            </button>
          </div>
        </div>

        {!query.isLoading && !query.isError && games.length > 0 ? (
          <p
            role="status"
            aria-live="polite"
            className="gf-page-muted mb-4 text-[11px] font-medium uppercase tracking-wider"
          >
            {t('discoverResultCount').replace('{n}', String(filtered.length))}
          </p>
        ) : null}

        {query.isLoading ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : query.isError ? (
          <div role="alert" className="gf-glass flex flex-col items-start gap-3 rounded-2xl p-6">
            <p className="flex items-center gap-2 text-sm text-rose-500">
              <AlertTriangle className="h-4 w-4" />
              {t('loadFailed')}
            </p>
            <button
              type="button"
              onClick={() => void query.refetch()}
              className="gf-interactive gf-btn-primary inline-flex cursor-pointer items-center gap-1.5 px-3 text-xs"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              {t('discoverRetry')}
            </button>
          </div>
        ) : games.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
            <div className="gf-glass flex h-16 w-16 items-center justify-center rounded-2xl">
              <Gamepad2 className="gf-text-accent h-7 w-7" />
            </div>
            <p className="gf-page-muted max-w-sm text-sm">{t('discoverEmpty')}</p>
            <Link
              to={token ? '/forge' : '/register'}
              className="gf-interactive gf-btn-primary inline-flex cursor-pointer items-center gap-1.5 !rounded-full px-5 py-2.5 text-sm"
            >
              {t('discoverEmptyCta')}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
            <div className="gf-glass flex h-16 w-16 items-center justify-center rounded-2xl">
              <Search className="gf-text-accent h-7 w-7" />
            </div>
            <p className="gf-page-muted text-sm">{t('discoverNoResults')}</p>
            {hasFilters ? (
              <button
                type="button"
                onClick={clearFilters}
                className="gf-interactive gf-chip inline-flex cursor-pointer items-center gap-1.5 rounded-full px-4 py-2 text-xs hover:text-[var(--gf-text)]"
              >
                {t('discoverClearFilter')}
              </button>
            ) : null}
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((g) => (
              <PublicGameCard key={g.game_id} game={g} variant="theme" />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
