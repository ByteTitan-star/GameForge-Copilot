import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Clock3, FolderOpen, Globe2, Heart, PenLine, Plus, Search, Sparkles, X } from 'lucide-react'
import { gamesApi } from '@/api/games'
import { reactionsApi } from '@/api/reactions'
import { GameStatus } from '@/api/enums'
import { formatApiError } from '@/api/error-message'
import type { GameSummary } from '@/api/types'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { isTrialUser } from '@/lib/trial'
import { DeleteConfirmModal } from './DeleteConfirmModal'
import { GameCard } from './GameCard'
import { GameDetailDrawer } from './GameDetailDrawer'

import type { MessageKey } from '@/i18n/messages'

const filterIds = ['all', 'draft', 'published', 'pipeline', 'favorites'] as const
const filterLabelKey: Record<(typeof filterIds)[number], MessageKey> = {
  all: 'filterAll',
  draft: 'filterDraft',
  published: 'filterPublished',
  pipeline: 'filterPipeline',
  favorites: 'filterFavorites',
}

const filterIcons = {
  all: FolderOpen,
  draft: PenLine,
  published: Globe2,
  pipeline: Clock3,
  favorites: Heart,
} as const

const EMPTY_GAMES: GameSummary[] = []

export function GameDashboard() {
  const t = useT()
  const qc = useQueryClient()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const trial = isTrialUser(user)
  const [filter, setFilter] = useState<(typeof filterIds)[number]>('all')
  const [q, setQ] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<GameSummary | null>(null)
  const [detailGame, setDetailGame] = useState<GameSummary | null>(null)
  const [exitingId, setExitingId] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['games', user?.user_id],
    enabled: Boolean(token && user),
    queryFn: () => gamesApi.list(token!),
  })

  const favoritesQ = useQuery({
    queryKey: ['favorites', user?.user_id],
    enabled: Boolean(token && user),
    queryFn: () => reactionsApi.listFavorites(token!),
  })

  const rows = query.data?.data ?? EMPTY_GAMES

  const counts = useMemo(() => {
    const draft = rows.filter(
      (g) => g.status === GameStatus.draft || g.status === GameStatus.rejected,
    ).length
    const published = rows.filter((g) => g.status === GameStatus.published).length
    const pipeline = rows.filter(
      (g) => g.status === GameStatus.submitted || g.status === GameStatus.reviewing,
    ).length
    return { all: rows.length, draft, published, pipeline, favorites: favoritesQ.data?.length ?? 0 }
  }, [rows, favoritesQ.data?.length])

  const list = useMemo(() => {
    if (filter === 'favorites') {
      const favRows = favoritesQ.data ?? []
      return favRows
        .filter((g) => !q || g.title.toLowerCase().includes(q.toLowerCase()))
        .map(
          (g) =>
            ({
              game_id: g.game_id,
              title: g.title,
              status: 'published',
              current_version: 1,
              slug: g.slug,
              updated_at: g.published_at,
            }) as GameSummary,
        )
    }
    return rows.filter((g) => {
      if (q && !g.title.toLowerCase().includes(q.toLowerCase())) return false
      if (filter === 'draft') return g.status === GameStatus.draft || g.status === GameStatus.rejected
      if (filter === 'published') return g.status === GameStatus.published
      if (filter === 'pipeline')
        return g.status === GameStatus.submitted || g.status === GameStatus.reviewing
      return true
    })
  }, [filter, q, rows, favoritesQ.data])

  const emptyTitleKey: MessageKey =
    q
      ? 'searchEmpty'
      : filter === 'favorites'
      ? 'favoritesEmpty'
      : filter === 'published'
        ? 'publishedEmpty'
        : filter === 'pipeline'
          ? 'pipelineEmpty'
          : 'noGames'

  const removeMu = useMutation({
    mutationFn: (gameId: string) => gamesApi.remove(gameId, token!),
    onSuccess: async () => {
      setDeleteTarget(null)
      setExitingId(null)
      await qc.invalidateQueries({ queryKey: ['games', user?.user_id] })
      setToast(t('deleted'))
    },
    onError: (e) => {
      setExitingId(null)
      setToast(formatApiError(e, t('deleteFailed')))
    },
  })

  const renameMu = useMutation({
    mutationFn: ({ gameId, title }: { gameId: string; title: string }) =>
      gamesApi.patch(gameId, { title }, token!),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['games', user?.user_id] })
      setToast(t('renamed'))
    },
    onError: (e) => {
      setToast(formatApiError(e, t('renameFailed')))
      throw e
    },
  })

  async function publishGame(g: GameSummary, note: string) {
    try {
      await gamesApi.submitPublish(g.game_id, g.current_version, note || t('defaultPublishNote'), token!)
      await qc.invalidateQueries({ queryKey: ['games', user?.user_id] })
      setToast(t('publishSubmitted'))
    } catch (e) {
      setToast(formatApiError(e, t('submitFailed')))
      throw e
    }
  }

  async function renameGame(g: GameSummary, title: string) {
    await renameMu.mutateAsync({ gameId: g.game_id, title })
  }

  function confirmDelete() {
    if (!deleteTarget) return
    const id = deleteTarget.game_id
    setDeleteTarget(null)
    setExitingId(id)
    window.setTimeout(() => removeMu.mutate(id), 320)
  }

  return (
    <div className="space-y-7">
      <header className="flex flex-col gap-5 border-b pb-6 gf-border-subtle lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-xl">
          <h1 className="gf-page-title">{t('games')}</h1>
          <p className="gf-page-subtitle mt-1.5 leading-relaxed">{t('gamesSubtitle')}</p>
        </div>
        <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
          <label className="relative block min-w-0 sm:w-72">
            <Search className="gf-page-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t('searchGamesPlaceholder')}
              className="gf-input h-11 w-full rounded-xl pl-9 pr-10 text-sm"
            />
            {q ? (
              <button
                type="button"
                title={t('clearSearch')}
                aria-label={t('clearSearch')}
                onClick={() => setQ('')}
                className="gf-page-muted gf-interactive absolute right-2 top-1/2 grid h-7 w-7 -translate-y-1/2 cursor-pointer place-items-center rounded-md hover:bg-black/[0.05] hover:text-[var(--gf-text)]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </label>
          {trial ? null : (
            <Link to="/forge" className="gf-btn-primary inline-flex h-11 shrink-0 items-center justify-center gap-2 px-5 text-sm">
              <Plus className="h-4 w-4" />
              {t('createGame')}
            </Link>
          )}
        </div>
      </header>

      {trial ? (
        <p role="status" className="gf-banner-warn rounded-xl px-3 py-2 text-sm">
          {t('trialGamesHint')}
        </p>
      ) : null}

      <section className="grid grid-cols-2 overflow-hidden border-y gf-border-subtle sm:grid-cols-5" aria-label={t('games')}>
        {filterIds.map((id) => {
          const Icon = filterIcons[id]
          const count = counts[id]
          return (
            <button
              key={id}
              type="button"
              onClick={() => setFilter(id)}
              aria-pressed={filter === id}
              className={cn(
                'gf-interactive relative flex min-h-22 cursor-pointer flex-col justify-between gap-3 border-b px-4 py-3 text-left last:col-span-2 last:border-b-0 even:border-l gf-border-subtle sm:last:col-span-1 sm:border-b-0 sm:border-r sm:even:border-l-0 sm:last:border-r-0',
                filter === id
                  ? 'bg-[rgba(var(--gf-primary-rgb),0.06)]'
                  : 'hover:bg-black/[0.025]',
              )}
            >
              <span className="flex items-center gap-2 text-xs font-medium gf-page-muted">
                <Icon className={cn('h-3.5 w-3.5', filter === id && 'gf-text-accent')} aria-hidden />
                {t(filterLabelKey[id])}
              </span>
              <span className="font-display text-2xl leading-none gf-page-body">{count}</span>
              {filter === id ? (
                <motion.span
                  layoutId="games-filter-indicator"
                  className="absolute inset-x-4 bottom-0 h-0.5 bg-[var(--gf-primary)]"
                  transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                />
              ) : null}
            </button>
          )
        })}
      </section>

      {toast ? (
        <div className="gf-banner-info flex items-center justify-between rounded-xl px-3 py-2 text-sm">
          <span>{toast}</span>
          <button type="button" className="gf-page-muted cursor-pointer" onClick={() => setToast(null)}>
            {t('close')}
          </button>
        </div>
      ) : null}

      {query.isLoading || (filter === 'favorites' && favoritesQ.isLoading) ? (
        <p className="gf-page-muted text-sm">{t('loading')}</p>
      ) : null}
      {query.isError ? (
        <p role="alert" className="text-sm text-rose-300">
          {formatApiError(query.error, t('loadFailed'))}
        </p>
      ) : null}

      {!query.isLoading && !(filter === 'favorites' && favoritesQ.isLoading) && list.length === 0 ? (
        <section className="flex min-h-90 flex-col items-center justify-center border-y px-6 py-16 text-center gf-border-subtle sm:py-20">
          <div className="gf-bg-accent-soft grid h-14 w-14 place-items-center rounded-xl gf-ring-accent">
            <Sparkles className="gf-text-accent h-6 w-6" aria-hidden />
          </div>
          <h2 className="gf-page-body mt-6 text-xl font-medium">{t(emptyTitleKey)}</h2>
          {filter === 'favorites' ? null : (
            <>
              <p className="gf-page-muted mt-2 max-w-sm text-sm leading-relaxed">
                {q ? t('searchEmptyHint') : t('noGamesHint')}
              </p>
              {trial ? null : (
                <Link to="/forge" className="gf-btn-primary mt-8 inline-flex items-center gap-2 px-6 py-3 text-sm">
                  <Plus className="h-4 w-4" />
                  {t('createFirstGame')}
                </Link>
              )}
            </>
          )}
        </section>
      ) : (
        <motion.div
          className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <AnimatePresence mode="popLayout">
            {list
              .filter((g) => g.game_id !== exitingId)
              .map((g) => (
                <motion.div
                  key={g.game_id}
                  layout
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                >
                  <GameCard
                    game={g}
                    readOnly={trial}
                    onPublish={publishGame}
                    onRequestDelete={setDeleteTarget}
                    onRename={trial ? undefined : renameGame}
                    onOpenDetail={g.current_version > 0 ? setDetailGame : undefined}
                  />
                </motion.div>
              ))}
          </AnimatePresence>
        </motion.div>
      )}

      <DeleteConfirmModal
        open={Boolean(deleteTarget)}
        title={deleteTarget?.title ?? ''}
        busy={removeMu.isPending}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />

      {token ? (
        <GameDetailDrawer
          game={detailGame}
          accessToken={token}
          readOnly={trial}
          onClose={() => setDetailGame(null)}
          onPublished={() => void qc.invalidateQueries({ queryKey: ['games', user?.user_id] })}
        />
      ) : null}
    </div>
  )
}
