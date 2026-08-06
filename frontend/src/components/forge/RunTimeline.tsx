import { cn } from '@/lib/cn'
import { RunPhase } from '@/api/enums'

export type TimelineItem = {
  id: string
  label: string
  detail?: string
  tone: 'info' | 'ok' | 'warn' | 'err' | 'muted'
  at: string
}

const PHASES: RunPhase[] = [
  RunPhase.plan,
  RunPhase.art,
  RunPhase.code,
  RunPhase.qa,
  RunPhase.done,
]

type Props = {
  phase: RunPhase | 'idle' | 'paused'
  items: TimelineItem[]
}

const toneClass: Record<TimelineItem['tone'], string> = {
  info: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100',
  ok: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100',
  warn: 'border-amber-400/35 bg-amber-400/10 text-amber-100',
  err: 'border-red-400/35 bg-red-400/10 text-red-100',
  muted: 'border-white/10 bg-white/[0.03] text-white/55',
}

export function RunTimeline({ phase, items }: Props) {
  const activeIdx = PHASES.indexOf(phase as RunPhase)

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#12151a]">
      <header className="border-b border-white/[0.06] px-4 py-3">
        <p className="font-mono text-[10px] tracking-[0.16em] text-white/40 uppercase">Pipeline</p>
        <p className="text-sm text-white/80">阶段时间线</p>
        <ol className="mt-3 flex flex-wrap gap-1.5">
          {PHASES.map((p, i) => {
            const done = activeIdx > i || phase === RunPhase.done
            const current = phase === p || (phase === 'paused' && p === RunPhase.plan && activeIdx <= 0)
            return (
              <li
                key={p}
                className={cn(
                  'rounded-md px-2 py-1 font-mono text-[10px] tracking-wider uppercase ring-1',
                  done && 'bg-emerald-400/15 text-emerald-200 ring-emerald-400/25',
                  current && !done && 'bg-cyan-400/15 text-cyan-100 ring-cyan-400/30',
                  !done && !current && 'bg-white/[0.03] text-white/35 ring-white/10',
                  phase === 'paused' && p === RunPhase.plan && 'bg-amber-400/15 text-amber-100 ring-amber-400/30',
                )}
              >
                {p}
              </li>
            )
          })}
        </ol>
      </header>

      <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {items.length === 0 ? (
          <p className="px-1 py-8 text-center text-sm text-white/35">发送需求后，事件将在此滚动出现</p>
        ) : (
          items.map((it) => (
            <article
              key={it.id}
              className={cn('rounded-xl border px-3 py-2.5', toneClass[it.tone])}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium">{it.label}</p>
                <time className="shrink-0 font-mono text-[10px] opacity-60">
                  {new Date(it.at).toLocaleTimeString()}
                </time>
              </div>
              {it.detail ? <p className="mt-1 text-xs opacity-80">{it.detail}</p> : null}
            </article>
          ))
        )}
      </div>
    </section>
  )
}
