import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Gamepad2, Plus, Search, Sparkles, Star, Trash2 } from 'lucide-react'
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
import { PublicGameCard } from './PublicGameCard'
import type { PublicGame } from '@/api/public-games'
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

type ConfirmState =
  | { kind: 'delete-single'; game: GameSummary }
  | { kind: 'delete-batch' }
  | { kind: 'unpublish'; game: GameSummary }
  | { kind: 'withdraw'; game: GameSummary }
  | null

export function GameDashboard() {
  const t = useT()
  const qc = useQueryClient()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const trial = isTrialUser(user)
  const [filter, setFilter] = useState<(typeof filterIds)[number]>('all')
  const [q, setQ] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [confirm, setConfirm] = useState<ConfirmState>(null)
  const [detailGame, setDetailGame] = useState<GameSummary | null>(null)
  const [exitingId, setExitingId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const gamesKey = ['games', user?.user_id] as const

  const query = useQuery({
    queryKey: gamesKey,
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

  const favoriteList = useMemo(() => {
    const favRows = favoritesQ.data ?? []
    return favRows.filter((g) => !q || g.title.toLowerCase().includes(q.toLowerCase()))
  }, [favoritesQ.data, q])

  const ownedList = useMemo(() => {
    return rows.filter((g) => {
      if (q && !g.title.toLowerCase().includes(q.toLowerCase())) return false
      if (filter === 'draft') return g.status === GameStatus.draft || g.status === GameStatus.rejected
      if (filter === 'published') return g.status === GameStatus.published
      if (filter === 'pipeline')
        return g.status === GameStatus.submitted || g.status === GameStatus.reviewing
      return true
    })
  }, [filter, q, rows])

  const showingFavorites = filter === 'favorites'
  const list = showingFavorites ? [] : ownedList

  // favorites 视图为他人已发布游戏的只读集合；不参与多选/删除
  const selectable = !trial && !showingFavorites
  const listIds = useMemo(() => list.map((g) => g.game_id), [list])
  const allSelected = selectable && listIds.length > 0 && listIds.every((id) => selectedIds.has(id))

  function clearSelection() {
    setSelectedIds(new Set())
  }
  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  function toggleSelectAll() {
    setSelectedIds((prev) => {
      const all = listIds.every((id) => prev.has(id))
      return all ? new Set() : new Set(listIds)
    })
  }

  const emptyTitleKey: MessageKey =
    filter === 'favorites'
      ? 'favoritesEmpty'
      : filter === 'published'
        ? 'publishedEmpty'
        : filter === 'pipeline'
          ? 'pipelineEmpty'
          : filter === 'draft'
            ? 'draftEmpty'
            : 'noGames'

  const emptyHintKey: MessageKey =
    filter === 'favorites'
      ? 'favoritesEmptyHint'
      : filter === 'published'
        ? 'publishedEmptyHint'
        : filter === 'pipeline'
          ? 'pipelineEmptyHint'
          : filter === 'draft'
            ? 'draftEmptyHint'
            : 'noGamesHint'

  const removeMu = useMutation({
    mutationFn: (gameId: string) => gamesApi.remove(gameId, token!),
    onSuccess: async () => {
      setConfirm(null)
      setExitingId(null)
      await qc.invalidateQueries({ queryKey: gamesKey })
      setToast(t('deleted'))
    },
    onError: (e) => {
      setExitingId(null)
      setToast(formatApiError(e, t('deleteFailed')))
    },
  })

  const batchRemoveMu = useMutation({
    mutationFn: (ids: string[]) => gamesApi.removeBatch(ids, token!),
    onSuccess: async (data) => {
      setConfirm(null)
      clearSelection()
      await qc.invalidateQueries({ queryKey: gamesKey })
      const parts = [t('batchDeleted', { n: data.deleted.length })]
      if (data.failed.length > 0) parts.push(t('batchDeletePartial', { n: data.failed.length }))
      setToast(parts.join('；'))
    },
    onError: (e) => setToast(formatApiError(e, t('batchDeleteFailed'))),
  })

  const unpublishMu = useMutation({
    mutationFn: (gameId: string) => gamesApi.unpublish(gameId, token!),
    onSuccess: async () => {
      setConfirm(null)
      await qc.invalidateQueries({ queryKey: gamesKey })
      setToast(t('unpublished'))
    },
    onError: (e) => setToast(formatApiError(e, t('unpublishFailed'))),
  })

  const withdrawMu = useMutation({
    mutationFn: (gameId: string) => gamesApi.withdrawPublish(gameId, token!),
    onSuccess: async () => {
      setConfirm(null)
      await qc.invalidateQueries({ queryKey: gamesKey })
      setToast(t('withdrawn'))
    },
    onError: (e) => setToast(formatApiError(e, t('withdrawFailed'))),
  })

  const renameMu = useMutation({
    mutationFn: ({ gameId, title }: { gameId: string; title: string }) =>
      gamesApi.patch(gameId, { title }, token!),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: gamesKey })
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
      await qc.invalidateQueries({ queryKey: gamesKey })
      setToast(t('publishSubmitted'))
    } catch (e) {
      setToast(formatApiError(e, t('submitFailed')))
      throw e
    }
  }

  async function renameGame(g: GameSummary, title: string) {
    await renameMu.mutateAsync({ gameId: g.game_id, title })
  }

  function confirmAction() {
    if (!confirm) return
    if (confirm.kind === 'delete-single') {
      const id = confirm.game.game_id
      setConfirm(null)
      setExitingId(id)
      window.setTimeout(() => removeMu.mutate(id), 320)
    } else if (confirm.kind === 'delete-batch') {
      batchRemoveMu.mutate([...selectedIds])
    } else if (confirm.kind === 'unpublish') {
      unpublishMu.mutate(confirm.game.game_id)
    } else if (confirm.kind === 'withdraw') {
      withdrawMu.mutate(confirm.game.game_id)
    }
  }

  // 统一确认弹窗渲染：根据 confirm 派生 badge/headline/body/confirmLabel/tone
  const busy =
    removeMu.isPending ||
    batchRemoveMu.isPending ||
    unpublishMu.isPending ||
    withdrawMu.isPending
  const modalProps = (() => {
    if (!confirm) return null
    if (confirm.kind === 'delete-single') {
      return {
        badge: 'Delete',
        headline: t('deleteConfirmTitle'),
        body: t('deleteConfirmBody', { title: confirm.game.title }),
        confirmLabel: t('confirmDelete'),
        tone: 'danger' as const,
      }
    }
    if (confirm.kind === 'delete-batch') {
      return {
        badge: 'Delete',
        headline: t('batchDeleteConfirmTitle', { n: selectedIds.size }),
        body: t('batchDeleteConfirmBody'),
        confirmLabel: t('confirmDelete'),
        tone: 'danger' as const,
      }
    }
    if (confirm.kind === 'unpublish') {
      return {
        badge: 'Unpublish',
        headline: t('unpublishConfirmTitle'),
        body: t('unpublishConfirmBody', { title: confirm.game.title }),
        confirmLabel: t('unpublish'),
        tone: 'warn' as const,
      }
    }
    return {
      badge: 'Withdraw',
      headline: t('withdrawConfirmTitle'),
      body: t('withdrawConfirmBody', { title: confirm.game.title }),
      confirmLabel: t('withdrawReview'),
      tone: 'warn' as const,
    }
  })()

  return (
    <div className="gf-games-dashboard space-y-5 md:space-y-6">
      <header className="flex flex-col gap-4 sm:gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h1 className="text-[26px] font-bold tracking-tight text-[var(--gf-text)] md:text-[28px]">
            {t('games')}
          </h1>
          <p className="gf-page-subtitle mt-1.5 text-sm leading-relaxed">{t('gamesSubtitle')}</p>
        </div>
        <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
          <label className="relative block w-full sm:w-[300px]">
            <Search className="gf-page-muted pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2" />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value)
                clearSelection()
              }}
              placeholder={t('searchGamesPlaceholder')}
              className="gf-input h-11 w-full rounded-[12px] pl-10 pr-3 text-sm"
            />
          </label>
          {trial ? null : (
            <Link
              to="/forge"
              className="gf-btn-primary inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-[10px] px-5 text-sm font-semibold shadow-[0_6px_16px_rgba(var(--gf-primary-rgb),0.22)] transition hover:-translate-y-0.5 hover:shadow-[0_10px_22px_rgba(var(--gf-primary-rgb),0.28)]"
            >
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

      <div className="-mx-1 overflow-x-auto px-1 pb-0.5">
        <div
          role="tablist"
          aria-label={t('games')}
          className="inline-flex min-w-full gap-1.5 rounded-xl border border-[var(--gf-border)] bg-[var(--gf-surface)] p-1 sm:min-w-0"
        >
          {filterIds.map((id) => {
            const count = counts[id]
            const active = filter === id
            return (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => {
                  setFilter(id)
                  clearSelection()
                }}
                className={cn(
                  'gf-interactive inline-flex h-9 shrink-0 cursor-pointer items-center gap-2 rounded-[8px] px-3.5 text-sm font-medium transition',
                  active
                    ? 'bg-[rgba(var(--gf-primary-rgb),0.12)] text-[var(--gf-primary)] shadow-[inset_0_0_0_1px_rgba(var(--gf-primary-rgb),0.22)]'
                    : 'gf-page-muted hover:bg-black/[0.03] hover:text-[var(--gf-text)]',
                )}
              >
                {id === 'favorites' ? <Star className="h-3.5 w-3.5 opacity-80" aria-hidden /> : null}
                <span>{t(filterLabelKey[id])}</span>
                <span
                  className={cn(
                    'inline-flex min-w-[1.25rem] items-center justify-center rounded-md px-1.5 py-0.5 font-mono text-[11px] leading-none',
                    active
                      ? 'bg-[rgba(var(--gf-primary-rgb),0.16)] text-[var(--gf-primary)]'
                      : 'bg-black/[0.04] text-[var(--gf-text-muted)]',
                  )}
                >
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {selectable && selectedIds.size > 0 ? (
        <div className="gf-glass flex flex-wrap items-center gap-3 rounded-xl px-4 py-2.5 text-sm">
          <span className="gf-page-body font-medium">{t('selectedCount', { n: selectedIds.size })}</span>
          <button
            type="button"
            onClick={toggleSelectAll}
            className="gf-page-muted gf-interactive cursor-pointer text-xs hover:underline"
          >
            {allSelected ? t('deselectAll') : t('selectAll')}
          </button>
          <button
            type="button"
            onClick={() => setConfirm({ kind: 'delete-batch' })}
            className="ml-auto inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-rose-300 ring-1 ring-rose-400/25 transition hover:bg-rose-500/10"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {t('batchDelete')}
          </button>
        </div>
      ) : null}

      {toast ? (
        <div className="gf-banner-info flex items-center justify-between rounded-xl px-3 py-2 text-sm">
          <span>{toast}</span>
          <button type="button" className="gf-page-muted cursor-pointer" onClick={() => setToast(null)}>
            {t('close')}
          </button>
        </div>
      ) : null}

      {query.isLoading || (showingFavorites && favoritesQ.isLoading) ? (
        <p className="gf-page-muted text-sm">{t('loading')}</p>
      ) : null}
      {query.isError ? (
        <p role="alert" className="text-sm text-rose-300">
          {formatApiError(query.error, t('loadFailed'))}
        </p>
      ) : null}

      {!query.isLoading &&
      !(showingFavorites && favoritesQ.isLoading) &&
      (showingFavorites ? favoriteList.length === 0 : list.length === 0) ? (
        <div className="flex flex-col items-center rounded-2xl border border-dashed border-[var(--gf-border)] bg-[var(--gf-surface)] px-6 py-16 text-center md:py-20">
          <div className="relative">
            <div className="gf-empty-glow absolute inset-0 scale-150 rounded-full blur-3xl" aria-hidden />
            <div className="gf-empty-icon-wrap relative grid h-20 w-20 place-items-center rounded-2xl border">
              {filter === 'favorites' ? (
                <Star className="gf-text-accent h-9 w-9" />
              ) : filter === 'pipeline' ? (
                <Gamepad2 className="gf-text-accent h-9 w-9" />
              ) : (
                <Sparkles className="gf-text-accent h-9 w-9" />
              )}
            </div>
          </div>
          <h2 className="gf-page-body mt-8 text-xl font-semibold tracking-tight">{t(emptyTitleKey)}</h2>
          <p className="gf-page-muted mt-2 max-w-sm text-sm leading-relaxed">{t(emptyHintKey)}</p>
          {filter === 'favorites' || trial ? null : (
            <Link
              to="/forge"
              className="gf-btn-primary mt-8 inline-flex items-center gap-2 rounded-[10px] px-6 py-3 text-sm font-semibold"
            >
              <Plus className="h-4 w-4" />
              {filter === 'all' ? t('createFirstGame') : t('createGame')}
            </Link>
          )}
        </div>
      ) : showingFavorites ? (
        <motion.div
          className="grid grid-cols-1 gap-5 sm:grid-cols-2 min-[1500px]:grid-cols-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {favoriteList.map((g: PublicGame) => (
            <PublicGameCard key={g.game_id} game={g} variant="theme" showFeaturedBadge={false} />
          ))}
        </motion.div>
      ) : (
        <motion.div
          className="grid grid-cols-1 gap-5 sm:grid-cols-2 min-[1500px]:grid-cols-3"
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
                    selectable={selectable}
                    selected={selectedIds.has(g.game_id)}
                    onToggleSelect={toggleSelect}
                    onPublish={publishGame}
                    onRequestDelete={setConfirmStateDeleteSingle}
                    onRequestUnpublish={trial ? undefined : setConfirmStateUnpublish}
                    onRequestWithdraw={trial ? undefined : setConfirmStateWithdraw}
                    onRename={trial ? undefined : renameGame}
                    onOpenDetail={g.current_version > 0 ? setDetailGame : undefined}
                  />
                </motion.div>
              ))}
          </AnimatePresence>
        </motion.div>
      )}

      {modalProps ? (
        <DeleteConfirmModal
          open
          badge={modalProps.badge}
          headline={modalProps.headline}
          body={modalProps.body}
          confirmLabel={modalProps.confirmLabel}
          tone={modalProps.tone}
          busy={busy}
          onCancel={() => setConfirm(null)}
          onConfirm={confirmAction}
        />
      ) : null}

      {token ? (
        <GameDetailDrawer
          game={detailGame}
          accessToken={token}
          readOnly={trial}
          onClose={() => setDetailGame(null)}
          onPublished={() => void qc.invalidateQueries({ queryKey: gamesKey })}
        />
      ) : null}
    </div>
  )

  function setConfirmStateDeleteSingle(game: GameSummary) {
    setConfirm({ kind: 'delete-single', game })
  }
  function setConfirmStateUnpublish(game: GameSummary) {
    setConfirm({ kind: 'unpublish', game })
  }
  function setConfirmStateWithdraw(game: GameSummary) {
    setConfirm({ kind: 'withdraw', game })
  }
}
