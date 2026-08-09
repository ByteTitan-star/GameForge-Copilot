import { cn } from '@/lib/cn'
import { RunPhase } from '@/api/enums'
import { useT } from '@/i18n/use-t'

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
  /** 是否渲染内置的「生成流程 + 阶段 chips」表头；底部日志带已在外层展示 StagePipeline，传 false 去重 */
  showHeader?: boolean
  className?: string
}

const toneClass: Record<TimelineItem['tone'], string> = {
  info: 'border-[#5271ff]/25 bg-[#5271ff]/[0.08] text-[#3046a8]',
  ok: 'border-[#1b9a6c]/25 bg-[#1b9a6c]/[0.08] text-[#167052]',
  warn: 'border-[#d49d12]/30 bg-[#ffcf5a]/15 text-[#785d14]',
  err: 'border-[#d84d3e]/25 bg-[#ff705c]/10 text-[#8e2f26]',
  muted: 'border-black/10 bg-black/[0.03] text-[#69737c]',
}

export function RunTimeline({ phase, items, showHeader = true, className }: Props) {
  const t = useT()
  const phaseLabels: Record<RunPhase, string> = {
    [RunPhase.plan]: t('phasePlan'),
    [RunPhase.art]: t('phaseArt'),
    [RunPhase.code]: t('phaseCode'),
    [RunPhase.qa]: t('phaseQa'),
    [RunPhase.done]: t('phaseDone'),
  }
  const activeIdx = PHASES.indexOf(phase as RunPhase)

  return (
    <section className={cn('flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-black/[0.08] bg-white', className)}>
      {showHeader ? (
        <header className="border-b border-black/[0.07] px-4 py-3">
          <p className="text-sm font-medium text-[#20262d]">{t('generationFlow')}</p>
          <ol className="mt-3 flex flex-wrap gap-1.5">
            {PHASES.map((p, i) => {
              const done = activeIdx > i || phase === RunPhase.done
              const current = phase === p || (phase === 'paused' && p === RunPhase.plan && activeIdx <= 0)
              return (
                <li
                  key={p}
                  className={cn(
                    'rounded-md px-2 py-1 font-mono text-[10px] tracking-wider uppercase ring-1',
                    done && 'bg-[#1b9a6c]/12 text-[#167052] ring-[#1b9a6c]/25',
                    current && !done && 'bg-[#5271ff]/12 text-[#3046a8] ring-[#5271ff]/25',
                    !done && !current && 'bg-black/[0.03] text-[#9099a1] ring-black/10',
                    phase === 'paused' && p === RunPhase.plan && 'bg-[#ffcf5a]/20 text-[#785d14] ring-[#d49d12]/25',
                  )}
                >
                  {phaseLabels[p]}
                </li>
              )
            })}
          </ol>
        </header>
      ) : null}

      <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {items.length === 0 ? (
          <p className="px-1 py-8 text-center text-sm text-[#9099a1]">{t('timelineEmpty')}</p>
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
