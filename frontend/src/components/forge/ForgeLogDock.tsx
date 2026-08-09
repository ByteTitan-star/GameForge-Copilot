import { ChevronDown, ChevronUp } from 'lucide-react'
import { RunPhase } from '@/api/enums'
import { FailureRecoveryBar } from '@/components/forge/FailureRecoveryBar'
import { RunTimeline, type TimelineItem } from '@/components/forge/RunTimeline'
import { StagePipeline } from '@/components/forge/StagePipeline'
import type { StagePipelineState } from '@/lib/stage-pipeline-state'
import { useT } from '@/i18n/use-t'

/** 失败恢复卡所需的上下文（来自 ForgePage） */
export type ForgeLogDockFailure = {
  runId: string
  errorSummary?: string
  onRevise: () => void
  onRetry: () => void
  busy?: boolean
}

type Props = {
  /** 是否展开日志带 body（标题栏始终常驻） */
  open: boolean
  onToggle: () => void
  runPhase: RunPhase | 'idle' | 'paused'
  stages: StagePipelineState
  items: TimelineItem[]
  currentModel?: string | null
  failureRecovery?: ForgeLogDockFailure | null
}

/**
 * 底部横跨的「执行日志带」：标题栏常驻（执行日志 · N + currentModel + 折叠），
 * 展开后依次展示 失败恢复 → 4 阶段进度（单行）→ 事件流（自身滚动）。
 * 与左栏聊天、右栏试玩物理分离，互不挤占宽度。
 */
export function ForgeLogDock({
  open,
  onToggle,
  runPhase,
  stages,
  items,
  currentModel,
  failureRecovery,
}: Props) {
  const t = useT()
  const showPipeline = runPhase !== 'idle' || items.length > 0

  return (
    <section className="gf-forge-log-dock" aria-label={t('eventLog')}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="gf-interactive gf-forge-log-dock-header flex w-full cursor-pointer items-center justify-between gap-2 text-left transition hover:bg-black/[0.02]"
      >
        <span className="flex items-center gap-1.5 font-mono text-[11px] tracking-wide text-[var(--gf-text-muted)] uppercase">
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
          {t('eventLog')}
          <span className="font-mono text-[10px]">· {items.length}</span>
        </span>
        {currentModel ? (
          <span className="font-mono text-[10px] text-[var(--gf-text-muted)]">
            {t('currentModel')}: {currentModel}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="gf-forge-log-dock-body">
          {failureRecovery ? (
            <FailureRecoveryBar
              runId={failureRecovery.runId}
              errorSummary={failureRecovery.errorSummary}
              onRevise={failureRecovery.onRevise}
              onRetry={failureRecovery.onRetry}
              busy={failureRecovery.busy}
            />
          ) : null}
          {showPipeline ? <StagePipeline runPhase={runPhase} stages={stages} columns={4} /> : null}
          <div className="gf-forge-log-dock-timeline">
            <RunTimeline phase={runPhase} items={items} showHeader={false} />
          </div>
        </div>
      ) : null}
    </section>
  )
}
