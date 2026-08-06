import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Plus, Search, Trash2, Upload } from 'lucide-react'
import { gamesApi } from '@/api/games'
import { GameStatus } from '@/api/enums'
import { ApiError } from '@/api/errors'
import type { GameSummary } from '@/api/types'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/cn'

const filters = [
  { id: 'all', label: '全部' },
  { id: 'draft', label: '草稿' },
  { id: 'published', label: '已发布' },
  { id: 'pipeline', label: '审批中' },
] as const

const coverClass = [
  'from-emerald-700/80 via-cyan-900/90 to-[#0b0d10]',
  'from-orange-700/70 via-rose-950/90 to-[#0b0d10]',
  'from-sky-800/70 via-slate-900 to-[#0b0d10]',
  'from-zinc-700/60 via-zinc-900 to-[#0b0d10]',
]

function coverFor(id: string) {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i) * (i + 1)) % coverClass.length
  return coverClass[h]
}

function statusTone(status: GameStatus) {
  switch (status) {
    case GameStatus.published:
      return 'bg-emerald-400/15 text-emerald-200 ring-emerald-400/25'
    case GameStatus.submitted:
    case GameStatus.reviewing:
      return 'bg-cyan-400/15 text-cyan-100 ring-cyan-400/25'
    case GameStatus.rejected:
    case GameStatus.taken_down:
      return 'bg-red-400/15 text-red-200 ring-red-400/25'
    default:
      return 'bg-white/[0.06] text-white/55 ring-white/10'
  }
}

export function GamesPage() {
  const t = useT()
  const qc = useQueryClient()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const [filter, setFilter] = useState<(typeof filters)[number]['id']>('all')
  const [q, setQ] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [publishId, setPublishId] = useState<string | null>(null)
  const [note, setNote] = useState('')

  const query = useQuery({
    queryKey: ['games', user?.user_id],
    enabled: Boolean(token && user),
    queryFn: () => gamesApi.list(token!),
  })

  const removeMu = useMutation({
    mutationFn: (gameId: string) => gamesApi.remove(gameId, token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['games', user?.user_id] })
      setConfirmId(null)
      setToast('已删除')
    },
    onError: (e) => {
      setToast(e instanceof ApiError ? e.message : '删除失败')
      setConfirmId(null)
    },
  })

  const publishMu = useMutation({
    mutationFn: (g: GameSummary) =>
      gamesApi.submitPublish(g.game_id, g.current_version, note || '申请上架', token!),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['games', user?.user_id] })
      setPublishId(null)
      setNote('')
      setToast('已提交发布审批')
    },
    onError: (e) => setToast(e instanceof ApiError ? e.message : '提交失败'),
  })

  const list = useMemo(() => {
    const rows = query.data?.data ?? []
    return rows.filter((g) => {
      if (q && !g.title.toLowerCase().includes(q.toLowerCase())) return false
      if (filter === 'draft') return g.status === GameStatus.draft || g.status === GameStatus.rejected
      if (filter === 'published') return g.status === GameStatus.published
      if (filter === 'pipeline')
        return g.status === GameStatus.submitted || g.status === GameStatus.reviewing
      return true
    })
  }, [filter, q, query.data?.data])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] tracking-[0.16em] text-white/35 uppercase">Library</p>
          <h1 className="text-2xl tracking-tight text-white/95 md:text-3xl">{t('games')}</h1>
          <p className="mt-1 text-sm text-white/40">草稿私有；提交后进入审批；通过后公开试玩。</p>
        </div>
        <Link to="/forge">
          <Button className="!rounded-lg !bg-teal-400 !px-4 !py-2.5 !text-black hover:!bg-teal-300">
            <Plus className="h-4 w-4" />
            {t('startForge')}
          </Button>
        </Link>
      </div>

      {toast ? (
        <div className="flex items-center justify-between rounded-xl bg-white/[0.05] px-3 py-2 text-sm text-white/75 ring-1 ring-white/10">
          <span>{toast}</span>
          <button type="button" className="cursor-pointer text-white/40 hover:text-white" onClick={() => setToast(null)}>
            关闭
          </button>
        </div>
      ) : null}

      <div className="flex flex-col gap-3 rounded-2xl border border-white/[0.06] bg-[#12151a] p-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-1">
          {filters.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={cn(
                'cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                filter === f.id
                  ? 'bg-white/[0.1] text-white'
                  : 'text-white/45 hover:bg-white/[0.05] hover:text-white/80',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <label className="relative block md:w-64">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索标题…"
            className="h-10 w-full rounded-xl border border-white/[0.08] bg-black/30 pl-9 pr-3 text-sm text-white outline-none placeholder:text-white/30 focus:ring-2 focus:ring-teal-400/25"
          />
        </label>
      </div>

      {query.isLoading ? <p className="text-sm text-white/40">加载中…</p> : null}
      {query.isError ? (
        <p role="alert" className="text-sm text-red-300">
          加载失败
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {list.map((g) => {
          const playTo =
            g.status === GameStatus.published && g.slug
              ? `/play/${g.slug}`
              : g.current_version > 0
                ? `/draft/${g.game_id}/${g.current_version}`
                : null
          const canPublish =
            g.current_version > 0 &&
            (g.status === GameStatus.draft ||
              g.status === GameStatus.rejected ||
              g.status === GameStatus.taken_down)
          const canDelete =
            g.status === GameStatus.draft ||
            g.status === GameStatus.rejected ||
            g.status === GameStatus.taken_down

          return (
            <article
              key={g.game_id}
              className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#12151a] transition-transform duration-200 hover:-translate-y-0.5"
            >
              <div className={cn('relative h-28 bg-gradient-to-br', coverFor(g.game_id))}>
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.12),transparent_45%)]" />
                <span
                  className={cn(
                    'absolute top-3 right-3 rounded-md px-2 py-0.5 font-mono text-[10px] tracking-wider uppercase ring-1',
                    statusTone(g.status),
                  )}
                >
                  {g.status}
                </span>
              </div>
              <div className="p-4">
                <h2 className="text-lg text-white/95">{g.title}</h2>
                <p className="mt-1 font-mono text-[11px] text-white/35">
                  v{g.current_version} · {new Date(g.updated_at).toLocaleString()}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link to={`/forge/${g.game_id}`}>
                    <Button
                      variant="ghost"
                      className="!rounded-lg !px-3 !py-1.5 text-xs text-white/75 ring-1 ring-white/10 hover:bg-white/[0.06]"
                    >
                      编辑
                    </Button>
                  </Link>
                  {playTo ? (
                    <Link to={playTo}>
                      <Button className="!rounded-lg !bg-white !px-3 !py-1.5 !text-xs !text-black hover:!bg-white/90">
                        {g.status === GameStatus.published ? '试玩' : '预览'}
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </Button>
                    </Link>
                  ) : null}
                  {canPublish ? (
                    <Button
                      variant="ghost"
                      className="!rounded-lg !px-3 !py-1.5 text-xs text-teal-200/90 ring-1 ring-teal-400/25 hover:bg-teal-400/10"
                      onClick={() => {
                        setPublishId(g.game_id)
                        setNote('')
                      }}
                    >
                      <Upload className="h-3.5 w-3.5" />
                      发布
                    </Button>
                  ) : null}
                  {canDelete ? (
                    <Button
                      variant="ghost"
                      className="!rounded-lg !px-3 !py-1.5 text-xs text-red-200/80 ring-1 ring-red-400/20 hover:bg-red-500/10"
                      onClick={() => setConfirmId(g.game_id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      删除
                    </Button>
                  ) : null}
                </div>

                {publishId === g.game_id ? (
                  <div className="mt-3 space-y-2 rounded-xl border border-teal-400/20 bg-teal-500/[0.06] p-3">
                    <p className="text-xs text-teal-100/80">提交 v{g.current_version} 进入审批</p>
                    <input
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="备注（可选）"
                      className="h-9 w-full rounded-lg border border-white/10 bg-black/30 px-2.5 text-sm text-white outline-none focus:ring-2 focus:ring-teal-400/25"
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        className="!rounded-lg !px-3 !py-1.5 text-xs text-white/50"
                        onClick={() => setPublishId(null)}
                      >
                        取消
                      </Button>
                      <Button
                        className="!rounded-lg !bg-teal-400 !px-3 !py-1.5 !text-xs !text-black"
                        disabled={publishMu.isPending}
                        onClick={() => publishMu.mutate(g)}
                      >
                        确认提交
                      </Button>
                    </div>
                  </div>
                ) : null}

                {confirmId === g.game_id ? (
                  <div className="mt-3 space-y-2 rounded-xl border border-red-400/25 bg-red-500/[0.08] p-3">
                    <p className="text-xs text-red-100/85">确认删除「{g.title}」？此操作不可恢复（mock）。</p>
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        className="!rounded-lg !px-3 !py-1.5 text-xs text-white/50"
                        onClick={() => setConfirmId(null)}
                      >
                        取消
                      </Button>
                      <Button
                        variant="danger"
                        className="!rounded-lg !px-3 !py-1.5 text-xs"
                        disabled={removeMu.isPending}
                        onClick={() => removeMu.mutate(g.game_id)}
                      >
                        确认删除
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            </article>
          )
        })}
      </div>

      {!query.isLoading && list.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 bg-[#12151a] px-6 py-16 text-center">
          <p className="text-lg text-white/85">还没有游戏</p>
          <p className="mt-2 text-sm text-white/40">去工坊用一句话开一款。</p>
          <Link to="/forge" className="mt-6 inline-flex">
            <Button className="!rounded-lg !bg-teal-400 !text-black hover:!bg-teal-300">{t('startForge')}</Button>
          </Link>
        </div>
      ) : null}
    </div>
  )
}
