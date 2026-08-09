import { RunPhase } from '@/api/enums'
import { cn } from '@/lib/cn'
import {
  formatEtaSeconds,
  PHASE_HUMAN_LABEL_KEYS,
  PHASE_ETA_SECONDS,
  PIPELINE_PHASES,
} from '@/lib/phase-labels'
import type { StagePipelineState } from '@/lib/stage-pipeline-state'
import { useT } from '@/i18n/use-t'

type Props = {
  runPhase: RunPhase | 'idle' | 'paused'
  stages: StagePipelineState
  /** 列数：默认 2（左栏纵向）；4 用于底部日志带的单行紧凑展示（窄屏回退 2 列） */
  columns?: 2 | 4
  className?: string
}

const phaseTitleKeys = {
  [RunPhase.plan]: 'phasePlan',
  [RunPhase.art]: 'phaseArt',
  [RunPhase.code]: 'phaseCode',
  [RunPhase.qa]: 'phaseQa',
} as const

export function StagePipeline({ runPhase, stages, columns = 2, className }: Props) {
  const t = useT()
  const gridCols = columns === 4 ? 'grid-cols-2 md:grid-cols-4' : 'sm:grid-cols-2'

  return (
    <section className={cn('space-y-2', className)} aria-label={t('generationFlow')}>
      <p className="font-mono text-[10px] tracking-[0.14em] gf-page-muted uppercase">{t('stagePipelineTitle')}</p>
      <ol className={cn('grid gap-2', gridCols)}>
        {PIPELINE_PHASES.map((phase) => {
          const info = stages[phase]
          const titleKey = phaseTitleKeys[phase as keyof typeof phaseTitleKeys]
          const human =
            info.humanLabel ??
            (info.status === 'active' || info.status === 'done'
              ? t(PHASE_HUMAN_LABEL_KEYS[phase])
              : t(PHASE_HUMAN_LABEL_KEYS[phase]))
          const etaSec = info.etaSeconds ?? PHASE_ETA_SECONDS[phase]
          const eta = info.status === 'active' && etaSec > 0 ? formatEtaSeconds(etaSec, t) : ''
          const isActive =
            info.status === 'active' ||
            (runPhase === phase && info.status !== 'done' && info.status !== 'failed')
          return (
            <li
              key={phase}
              className={cn(
                'rounded-xl border px-3 py-2.5 text-xs transition',
                info.status === 'failed' && 'border-rose-300/40 bg-rose-50/80 text-rose-900',
                info.status === 'done' && 'border-emerald-300/30 bg-emerald-50/60 text-emerald-900',
                isActive && info.status !== 'failed' && 'border-[rgba(var(--gf-primary-rgb),0.35)] bg-[rgba(var(--gf-primary-rgb),0.08)]',
                info.status === 'pending' && !isActive && 'gf-border-subtle border bg-black/[0.02] gf-page-muted',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium gf-page-body">{t(titleKey)}</span>
                <span className="font-mono text-[10px] uppercase opacity-70">{info.status}</span>
              </div>
              <p className="mt-1 leading-relaxed">{human}</p>
              {eta ? <p className="mt-1 font-mono text-[10px] opacity-65">{eta}</p> : null}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
