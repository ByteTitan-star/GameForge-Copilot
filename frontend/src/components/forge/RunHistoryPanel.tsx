import { useQuery } from '@tanstack/react-query'
import { Loader2, RotateCcw } from 'lucide-react'
import { gamesApi } from '@/api/games'
import type { RunListItem } from '@/api/types'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Props = {
  gameId: string
  accessToken: string
  currentRunId: string | null
  onReconnect: (run: RunListItem) => void
  reconnectingId?: string | null
  runErrors?: Record<string, string>
  className?: string
}

const statusTone: Record<string, string> = {
  running: 'text-emerald-600',
  paused: 'text-amber-600',
  done: 'text-slate-500',
  failed: 'text-rose-600',
}

export function RunHistoryPanel({
  gameId,
  accessToken,
  currentRunId,
  onReconnect,
  reconnectingId,
  runErrors,
  className,
}: Props) {
  const t = useT()
  const q = useQuery({
    queryKey: ['game-runs', gameId],
    queryFn: () => gamesApi.listRuns(gameId, accessToken),
    enabled: Boolean(gameId && accessToken),
  })

  const runs = q.data?.data ?? []

  return (
    <section className={cn('space-y-2', className)}>
      <p className="font-mono text-[10px] tracking-[0.14em] gf-page-muted uppercase">{t('runHistory')}</p>
      {q.isLoading ? (
        <p className="flex items-center gap-2 text-xs gf-page-muted">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {t('loading')}
        </p>
      ) : runs.length === 0 ? (
        <p className="text-xs gf-page-muted">{t('runHistoryEmpty')}</p>
      ) : (
        <ul className="max-h-48 space-y-1.5 overflow-y-auto">
          {runs.map((run) => {
            const active = run.run_id === currentRunId
            const canReconnect = run.status === 'running' || run.status === 'paused'
            const err = runErrors?.[run.run_id]
            return (
              <li
                key={run.run_id}
                className={cn(
                  'rounded-lg border px-3 py-2 text-xs transition',
                  active
                    ? 'gf-border-subtle border bg-[rgba(var(--gf-primary-rgb),0.08)]'
                    : 'gf-border-subtle border bg-black/[0.02]',
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-mono text-[10px] gf-page-body">{run.run_id.slice(0, 8)}…</p>
                    <p className={cn('mt-0.5 font-medium uppercase', statusTone[run.status] ?? 'gf-page-muted')}>
                      {run.status} · {run.phase}
                    </p>
                    <p className="mt-0.5 gf-page-muted">
                      {new Date(run.started_at).toLocaleString()}
                      {run.ended_at ? ` → ${new Date(run.ended_at).toLocaleString()}` : ''}
                    </p>
                    {run.status === 'failed' && err ? (
                      <p className="mt-1 text-rose-500">{err}</p>
                    ) : null}
                  </div>
                  {canReconnect ? (
                    <button
                      type="button"
                      disabled={reconnectingId === run.run_id}
                      onClick={() => onReconnect(run)}
                      className="gf-interactive gf-text-accent shrink-0 inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 text-[10px] uppercase tracking-wide hover:bg-black/[0.04]"
                    >
                      {reconnectingId === run.run_id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <RotateCcw className="h-3 w-3" />
                      )}
                      {t('runReconnect')}
                    </button>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
