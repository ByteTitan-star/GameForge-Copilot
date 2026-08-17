import { RunPhase } from '@/api/enums'
import { cn } from '@/lib/cn'
import { PIPELINE_PHASES } from '@/lib/phase-labels'
import type { StagePipelineState } from '@/lib/stage-pipeline-state'
import { useT } from '@/i18n/use-t'
import { Check, Circle, Loader2, X } from 'lucide-react'
import type { TimelineItem } from '@/components/forge/RunTimeline'

const phaseTitleKeys = {
  [RunPhase.plan]: 'phasePlan',
  [RunPhase.art]: 'phaseArt',
  [RunPhase.code]: 'phaseCode',
  [RunPhase.qa]: 'phaseQa',
} as const

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

const toneClass: Record<
  TimelineItem['tone'],
  { dot: string; icon: typeof Circle }
> = {
  info: {
    dot: 'border-[#5271ff]/30 bg-[#5271ff]/10 text-[#4057cc]',
    icon: Circle,
  },
  ok: { dot: 'border-emerald-300 bg-emerald-50 text-emerald-700', icon: Check },
  warn: {
    dot: 'border-amber-300 bg-amber-50 text-amber-700',
    icon: Circle,
  },
  err: { dot: 'border-rose-300 bg-rose-50 text-rose-700', icon: X },
  muted: {
    dot: 'border-black/10 bg-black/[0.03] text-[#69737c]',
    icon: Circle,
  },
}

type Props = {
  runPhase: RunPhase | 'idle' | 'paused'
  stages: StagePipelineState
  items: TimelineItem[]
  className?: string
}

function bucketItems(items: TimelineItem[]): Record<RunPhase, TimelineItem[]> {
  const buckets = Object.fromEntries(
    PIPELINE_PHASES.map((phase) => [phase, [] as TimelineItem[]]),
  ) as Record<RunPhase, TimelineItem[]>
  for (const item of items) {
    const phase = item.phase && PIPELINE_PHASES.includes(item.phase) ? item.phase : RunPhase.plan
    buckets[phase].push(item)
  }
  return buckets
}

/** 四列阶段日志：策划 / 美术 / 开发 / 测试 各挂载对应事件 */
export function StageLogGrid({ runPhase, stages, items, className }: Props) {
  const t = useT()
  const grouped = bucketItems(items)

  return (
    <div className={cn('gf-forge-stage-log-grid', className)} aria-label={t('generationFlow')}>
      {PIPELINE_PHASES.map((phase) => {
        const info = stages[phase]
        const titleKey = phaseTitleKeys[phase]
        const isActive =
          info.status === 'active' ||
          (runPhase === phase && info.status !== 'done' && info.status !== 'failed')
        const StatusIcon =
          info.status === 'failed'
            ? X
            : info.status === 'done'
              ? Check
              : isActive
                ? Loader2
                : Circle
        const columnItems = grouped[phase]

        return (
          <section key={phase} className="gf-forge-stage-log-col flex min-w-0 flex-col">
            <header className="gf-forge-stage-log-col-header flex items-center gap-1.5 border-b border-black/[0.06] pb-1.5">
              <span
                className={cn(
                  'grid h-5 w-5 shrink-0 place-items-center rounded-full border',
                  info.status === 'failed' && 'border-rose-300 bg-rose-100 text-rose-700',
                  info.status === 'done' && 'border-emerald-300 bg-emerald-100 text-emerald-700',
                  isActive &&
                    info.status !== 'failed' &&
                    'border-[rgba(var(--gf-primary-rgb),0.35)] bg-[rgba(var(--gf-primary-rgb),0.12)] gf-text-accent',
                  info.status === 'pending' &&
                    !isActive &&
                    'gf-border-subtle bg-[var(--gf-surface)] gf-page-muted',
                )}
              >
                <StatusIcon
                  className={cn(
                    'h-2.5 w-2.5',
                    isActive && 'animate-spin motion-reduce:animate-none',
                  )}
                  strokeWidth={2.2}
                  aria-hidden="true"
                />
              </span>
              <span className="truncate text-[12px] font-semibold gf-page-body">{t(titleKey)}</span>
            </header>
            <ol className="mt-1 min-h-0 flex-1 space-y-0.5 overflow-y-auto">
              {columnItems.length === 0 ? (
                <li className="px-1 py-3 text-center text-[11px] gf-page-muted">{t('timelineEmpty')}</li>
              ) : (
                columnItems.slice(0, 20).map((it) => {
                  const tone = toneClass[it.tone]
                  const ToneIcon = tone.icon
                  return (
                    <li
                      key={it.id}
                      className="flex gap-2 rounded-lg px-1 py-1.5 hover:bg-black/[0.02]"
                    >
                      <span
                        className={cn(
                          'mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full border',
                          tone.dot,
                        )}
                      >
                        <ToneIcon className="h-2 w-2" aria-hidden="true" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="break-words text-[11px] font-medium leading-snug text-[#303940]">
                          {it.label}
                        </p>
                        {it.detail ? (
                          <p className="mt-0.5 break-words text-[10px] leading-relaxed text-[#69737c]">
                            {it.detail}
                          </p>
                        ) : null}
                        <time className="mt-0.5 block font-mono text-[10px] tabular-nums text-[#9aa3ab]">
                          {timeFormatter.format(new Date(it.at))}
                        </time>
                      </div>
                    </li>
                  )
                })
              )}
            </ol>
          </section>
        )
      })}
    </div>
  )
}
