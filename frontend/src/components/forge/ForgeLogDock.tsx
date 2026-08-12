import { useCallback, useEffect, useRef, useState } from 'react'
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
  kind?: 'llm' | 'generic'
  onConfigureLlm?: () => void
}

type Props = {
  /** 是否展开日志带 body（标题栏始终常驻） */
  open: boolean
  onToggle: () => void
  runPhase: RunPhase | 'idle' | 'paused'
  stages: StagePipelineState
  items: TimelineItem[]
  failureRecovery?: ForgeLogDockFailure | null
}

const HEIGHT_KEY = 'gf-forge-log-height'
const DEFAULT_HEIGHT = 260
const MIN_HEIGHT = 120
/** 占视口高度的上限，避免日志长期挤占主工作区 */
const MAX_HEIGHT_RATIO = 0.45
/** 阻塞错误时自动撑开的高度 */
const BLOCKED_HEIGHT = 240

function readStoredHeight(): number {
  try {
    const raw = localStorage.getItem(HEIGHT_KEY)
    if (!raw) return DEFAULT_HEIGHT
    const n = Number(raw)
    if (!Number.isFinite(n)) return DEFAULT_HEIGHT
    return Math.max(MIN_HEIGHT, n)
  } catch {
    return DEFAULT_HEIGHT
  }
}

/**
 * 底部横跨的「执行日志带」：标题栏常驻（折叠时仅 44px，显示最新事件与错误数），
 * 展开后顶部可垂直拖拽调整高度（120px ~ 45vh，持久化）。失败恢复条固定可见；
 * 4 阶段进度（sticky 置顶）与事件流共享同一滚动容器，内容再多也能向下滚动到底。
 */
export function ForgeLogDock({
  open,
  onToggle,
  runPhase,
  stages,
  items,
  failureRecovery,
}: Props) {
  const t = useT()
  const showPipeline = runPhase !== 'idle' || items.length > 0
  const [height, setHeight] = useState(readStoredHeight)
  const draggingRef = useRef(false)
  const dockRef = useRef<HTMLElement | null>(null)

  const persistHeight = useCallback((next: number) => {
    const maxPx = Math.round(window.innerHeight * MAX_HEIGHT_RATIO)
    const clamped = Math.min(maxPx, Math.max(MIN_HEIGHT, next))
    setHeight(clamped)
    try {
      localStorage.setItem(HEIGHT_KEY, String(clamped))
    } catch {
      /* ignore quota errors */
    }
  }, [])

  useEffect(() => {
    function onMove(event: PointerEvent) {
      if (!draggingRef.current || !dockRef.current) return
      // 向上拖增大高度：新高度 = 抽屉底部 y - 指针 y
      const bottom = dockRef.current.getBoundingClientRect().bottom
      persistHeight(bottom - event.clientY)
    }
    function onUp() {
      draggingRef.current = false
      document.body.classList.remove('gf-forge-dock-resizing')
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      document.body.classList.remove('gf-forge-dock-resizing')
    }
  }, [persistHeight])

  // 阻塞性错误时自动撑开到可阅读高度（不永久占用，仅提升到 BLOCKED_HEIGHT）
  useEffect(() => {
    if (open && failureRecovery && height < BLOCKED_HEIGHT) {
      persistHeight(BLOCKED_HEIGHT)
    }
  }, [open, failureRecovery, height, persistHeight])

  const latest = items[0]
  const errorCount = items.filter((i) => i.tone === 'err').length

  return (
    <section ref={dockRef} className="gf-forge-log-dock" aria-label={t('eventLog')}>
      {open ? (
        <div
          role="separator"
          aria-orientation="horizontal"
          aria-label={t('forgeDragToResize')}
          tabIndex={0}
          className="gf-forge-dock-handle"
          onPointerDown={(event) => {
            event.preventDefault()
            draggingRef.current = true
            document.body.classList.add('gf-forge-dock-resizing')
          }}
        />
      ) : null}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="gf-interactive gf-forge-log-dock-header flex w-full cursor-pointer items-center justify-between gap-2 text-left transition hover:bg-black/[0.02]"
      >
        <span className="flex min-w-0 items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-[var(--gf-text-muted)]">
          {open ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0" />
          ) : (
            <ChevronUp className="h-3.5 w-3.5 shrink-0" />
          )}
          <span className="shrink-0">{t('eventLog')}</span>
          <span className="shrink-0 font-mono text-[11px]">· {items.length}</span>
          {!open && latest ? (
            <span className="min-w-0 truncate normal-case text-[var(--gf-text)] opacity-80">
              <span className="opacity-55">{t('forgeLogLatest')}:</span>{' '}
              {latest.label}
            </span>
          ) : null}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {!open && errorCount > 0 ? (
            <span className="font-mono text-[11px] text-rose-600">
              {t('forgeLogErrors', { n: errorCount })}
            </span>
          ) : null}
        </span>
      </button>

      {open ? (
        <div className="gf-forge-log-dock-body" style={{ height }}>
          {failureRecovery ? (
            <FailureRecoveryBar
              runId={failureRecovery.runId}
              errorSummary={failureRecovery.errorSummary}
              onRevise={failureRecovery.onRevise}
              onRetry={failureRecovery.onRetry}
              busy={failureRecovery.busy}
              kind={failureRecovery.kind}
              onConfigureLlm={failureRecovery.onConfigureLlm}
            />
          ) : null}
          {/* 失败恢复条固定可见；进度条与事件流共享同一滚动容器，
              进度条 sticky 置顶，事件再多也能向下滚动到底。 */}
          <div className="gf-forge-log-dock-scroll">
            {showPipeline ? (
              <div className="gf-forge-log-dock-sticky">
                <StagePipeline runPhase={runPhase} stages={stages} columns={4} />
              </div>
            ) : null}
            <RunTimeline
              phase={runPhase}
              items={items}
              showHeader={false}
              scrollable={false}
            />
          </div>
        </div>
      ) : null}
    </section>
  )
}
