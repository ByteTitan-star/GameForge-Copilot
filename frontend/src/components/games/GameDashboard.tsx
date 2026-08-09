import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Plus, Search, Sparkles } from 'lucide-react'
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

  const rows = query.data?.data ?? []

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
    filter === 'favorites'
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
    <div className="space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="gf-page-title">{t('games')}</h1>
          <p className="gf-page-subtitle mt-1">{t('gamesSubtitle')}</p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="relative block sm:w-72">
            <Search className="gf-page-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t('searchGamesPlaceholder')}
              className="gf-input h-11 w-full rounded-xl pl-9 pr-3 text-sm"
            />
          </label>
          {trial ? null : (
            <Link to="/forge" className="gf-btn-primary inline-flex h-11 items-center justify-center gap-2 px-5 text-sm">
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

      <div className="flex flex-wrap items-center gap-2">
        {filterIds.map((id) => {
          const count = counts[id]
          return (
            <button
              key={id}
              type="button"
              onClick={() => setFilter(id)}
              className={cn(
                'cursor-pointer rounded-xl px-3 py-2 text-xs font-medium transition',
                filter === id
                  ? 'gf-filter-active'
                  : 'gf-chip gf-interactive hover:bg-black/[0.03]',
              )}
            >
              {t(filterLabelKey[id])}
              <span className="ml-1.5 font-mono text-[10px] opacity-70">{count}</span>
            </button>
          )
        })}
      </div>

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
        <div className="gf-glass flex flex-col items-center rounded-2xl px-6 py-20 text-center">
          <div className="relative">
            <div className="gf-empty-glow absolute inset-0 scale-150 rounded-full blur-3xl" aria-hidden />
            <div className="gf-empty-icon-wrap relative grid h-20 w-20 place-items-center rounded-2xl border">
              <Sparkles className="gf-text-accent h-9 w-9" />
            </div>
          </div>
          <h2 className="gf-page-body mt-8 text-xl font-medium">{t(emptyTitleKey)}</h2>
          {filter === 'favorites' ? null : (
            <>
              <p className="gf-page-muted mt-2 max-w-sm text-sm leading-relaxed">{t('noGamesHint')}</p>
              {trial ? null : (
                <Link to="/forge" className="gf-btn-primary mt-8 inline-flex items-center gap-2 px-6 py-3 text-sm">
                  <Plus className="h-4 w-4" />
                  {t('createFirstGame')}
                </Link>
              )}
            </>
          )}
        </div>
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
