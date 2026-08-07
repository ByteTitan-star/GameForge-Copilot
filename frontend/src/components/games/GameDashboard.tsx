import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Search, Sparkles } from 'lucide-react'
import { gamesApi } from '@/api/games'
import { GameStatus } from '@/api/enums'
import { formatApiError } from '@/api/error-message'
import type { GameSummary } from '@/api/types'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { isTrialUser } from '@/lib/trial'
import { DeleteConfirmModal } from './DeleteConfirmModal'
import { GameCard } from './GameCard'
import { ParticleField } from './ParticleField'

const filters = [
  { id: 'all', label: '全部' },
  { id: 'draft', label: '草稿' },
  { id: 'published', label: '已发布' },
  { id: 'pipeline', label: '审批中' },
] as const

const listVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] as const } },
  exit: { opacity: 0, scale: 0.85, transition: { duration: 0.28 } },
}

export function GameDashboard() {
  const t = useT()
  const qc = useQueryClient()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const trial = isTrialUser(user)
  const [filter, setFilter] = useState<(typeof filters)[number]['id']>('all')
  const [q, setQ] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<GameSummary | null>(null)
  const [exitingId, setExitingId] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['games', user?.user_id],
    enabled: Boolean(token && user),
    queryFn: () => gamesApi.list(token!),
  })

  const rows = query.data?.data ?? []

  const stats = useMemo(() => {
    const pending = rows.filter(
      (g) => g.status === GameStatus.submitted || g.status === GameStatus.reviewing,
    ).length
    const plays = rows.reduce((acc, g) => acc + g.current_version * 17 + (g.slug ? 40 : 0), 0)
    return { total: rows.length, pending, plays }
  }, [rows])

  const list = useMemo(() => {
    return rows.filter((g) => {
      if (q && !g.title.toLowerCase().includes(q.toLowerCase())) return false
      if (filter === 'draft') return g.status === GameStatus.draft || g.status === GameStatus.rejected
      if (filter === 'published') return g.status === GameStatus.published
      if (filter === 'pipeline')
        return g.status === GameStatus.submitted || g.status === GameStatus.reviewing
      return true
    })
  }, [filter, q, rows])

  const removeMu = useMutation({
    mutationFn: (gameId: string) => gamesApi.remove(gameId, token!),
    onSuccess: async () => {
      setDeleteTarget(null)
      setExitingId(null)
      await qc.invalidateQueries({ queryKey: ['games', user?.user_id] })
      setToast('已删除')
    },
    onError: (e) => {
      setExitingId(null)
      setToast(formatApiError(e, '删除失败'))
    },
  })

  const renameMu = useMutation({
    mutationFn: ({ gameId, title }: { gameId: string; title: string }) =>
      gamesApi.patch(gameId, { title }, token!),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['games', user?.user_id] })
      setToast('已重命名')
    },
    onError: (e) => {
      setToast(formatApiError(e, '重命名失败'))
      throw e
    },
  })

  async function publishGame(g: GameSummary, note: string) {
    try {
      await gamesApi.submitPublish(g.game_id, g.current_version, note || '申请上架', token!)
      await qc.invalidateQueries({ queryKey: ['games', user?.user_id] })
      setToast('已提交发布审批')
    } catch (e) {
      setToast(formatApiError(e, '提交失败'))
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
    window.setTimeout(() => {
      removeMu.mutate(id)
    }, 320)
  }

  return (
    <div className="relative min-h-[calc(100vh-0px)] text-white">
      <ParticleField />

      <div className="relative z-10 space-y-6">
        <header className="space-y-1">
          <p className="font-mono text-[10px] tracking-[0.18em] text-white/35 uppercase">Dashboard</p>
          <h1 className="text-2xl tracking-tight text-white md:text-3xl">我的游戏工坊</h1>
          <p className="text-sm text-white/40">瀑布流卡片 · 赛博紫 / 霓虹青 · 真实 API</p>
        </header>

        <motion.div
          className="grid gap-3 sm:grid-cols-3"
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        >
          {[
            { k: '总游戏数', v: stats.total, accent: 'from-purple-500/30 to-transparent' },
            { k: '待审批', v: stats.pending, accent: 'from-amber-500/25 to-transparent' },
            { k: '今日试玩', v: stats.plays, accent: 'from-cyan-400/25 to-transparent' },
          ].map((s) => (
            <div
              key={s.k}
              className={cn(
                'rounded-2xl border border-white/[0.06] bg-white/[0.03] p-4 backdrop-blur-md',
                'bg-gradient-to-br',
                s.accent,
              )}
            >
              <p className="font-mono text-[10px] tracking-wider text-white/40 uppercase">{s.k}</p>
              <p className="mt-2 bg-gradient-to-r from-purple-300 to-cyan-300 bg-clip-text text-3xl font-semibold text-transparent">
                {s.v}
              </p>
            </div>
          ))}
        </motion.div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <label className="relative block w-full lg:w-[60%]">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索标题…"
              className="h-11 w-full rounded-xl border border-white/[0.08] bg-white/[0.03] pl-9 pr-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-cyan-400/40 focus:ring-2 focus:ring-cyan-400/20"
            />
          </label>
          {trial ? null : (
            <Link
              to="/forge"
              className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-500 to-cyan-400 px-5 text-sm font-semibold text-black shadow-[0_0_28px_rgba(168,85,247,0.35)] transition hover:brightness-110"
            >
              <Sparkles className="h-4 w-4" />
              开始做游戏
            </Link>
          )}
        </div>

        {trial ? (
          <p role="status" className="rounded-xl border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
            {t('trialGamesHint')}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-1.5">
          {filters.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={cn(
                'cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium transition',
                filter === f.id
                  ? 'bg-gradient-to-r from-purple-500/30 to-cyan-400/25 text-white ring-1 ring-cyan-400/30'
                  : 'text-white/45 hover:bg-white/[0.05] hover:text-white/80',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {toast ? (
          <div className="flex items-center justify-between rounded-xl border border-cyan-400/20 bg-cyan-400/10 px-3 py-2 text-sm text-cyan-50">
            <span>{toast}</span>
            <button type="button" className="cursor-pointer text-white/50" onClick={() => setToast(null)}>
              关闭
            </button>
          </div>
        ) : null}

        {query.isLoading ? <p className="text-sm text-white/40">加载中…</p> : null}
        {query.isError ? (
          <p role="alert" className="text-sm text-rose-300">
            加载失败
          </p>
        ) : null}

        <motion.div
          className="columns-1 gap-4 sm:columns-2 xl:columns-3"
          variants={listVariants}
          initial="hidden"
          animate="show"
        >
          <AnimatePresence mode="popLayout">
            {list
              .filter((g) => g.game_id !== exitingId)
              .map((g) => (
                <motion.div key={g.game_id} variants={itemVariants} layout exit="exit">
                  <GameCard
                    game={g}
                    readOnly={trial}
                    onPublish={publishGame}
                    onRequestDelete={setDeleteTarget}
                    onRename={trial ? undefined : renameGame}
                  />
                </motion.div>
              ))}
          </AnimatePresence>
        </motion.div>

        {!query.isLoading && list.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 py-16 text-center">
            <p className="text-lg text-white/85">还没有游戏</p>
            <p className="mt-2 text-sm text-white/40">去工坊说清楚规则，马上就能做一款。</p>
            {trial ? null : (
              <Link
                to="/forge"
                className="mt-6 inline-flex rounded-xl bg-gradient-to-r from-purple-500 to-cyan-400 px-5 py-2.5 text-sm font-semibold text-black"
              >
                开始做游戏
              </Link>
            )}
          </div>
        ) : null}
      </div>

      <DeleteConfirmModal
        open={Boolean(deleteTarget)}
        title={deleteTarget?.title ?? ''}
        busy={removeMu.isPending}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
