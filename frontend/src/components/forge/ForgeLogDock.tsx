import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { RunPhase } from '@/api/enums'
import { FailureRecoveryBar } from '@/components/forge/FailureRecoveryBar'
import { StageLogGrid } from '@/components/forge/StageLogGrid'
import type { TimelineItem } from '@/components/forge/RunTimeline'
import type { StagePipelineState } from '@/lib/stage-pipeline-state'
import { cn } from '@/lib/cn'
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
  /**
   * HITL 确认卡与日志带争用底部视口：为 true 时压低日志最大高度，
   * 避免展开后盖住聊天区底部的人工确认操作。
   */
  reserveForHitl?: boolean
}

const HEIGHT_KEY = 'gf-forge-log-height'
const DEFAULT_HEIGHT_RATIO = 0.22
const MIN_HEIGHT_RATIO = 0.12
const MAX_HEIGHT_RATIO = 0.42
const HITL_DEFAULT_HEIGHT_RATIO = 0.16
const HITL_MAX_HEIGHT_RATIO = 0.24

function readStoredHeight(): number | null {
  try {
    const raw = localStorage.getItem(HEIGHT_KEY)
    if (!raw) return null
    const n = Number(raw)
    if (!Number.isFinite(n)) return null
    return n
  } catch {
    return null
  }
}

function heroBasisPx(): number {
  const hero = document.querySelector('.gf-forge-hero')
  if (hero instanceof HTMLElement && hero.clientHeight > 0) {
    return hero.clientHeight
  }
  return window.innerHeight
}

function defaultHeightPx(reserveForHitl: boolean): number {
  const ratio = reserveForHitl ? HITL_DEFAULT_HEIGHT_RATIO : DEFAULT_HEIGHT_RATIO
  return Math.round(heroBasisPx() * ratio)
}

function minHeightPx(): number {
  return Math.round(heroBasisPx() * MIN_HEIGHT_RATIO)
}

function maxHeightPx(reserveForHitl: boolean): number {
  const ratio = reserveForHitl ? HITL_MAX_HEIGHT_RATIO : MAX_HEIGHT_RATIO
  return Math.round(heroBasisPx() * ratio)
}

/**
 * 底部横跨的「执行日志带」：默认折叠；展开后约占工坊高度 22%，可拖高；
 * 有 HITL 时进一步压低，避免遮挡聊天底部确认卡。
 */
export function ForgeLogDock({
  open,
  onToggle,
  runPhase,
  stages,
  items,
  failureRecovery,
  reserveForHitl = false,
}: Props) {
  const t = useT()
  const showGrid = runPhase !== 'idle' || items.length > 0
  const [height, setHeight] = useState(() => readStoredHeight() ?? defaultHeightPx(false))
  const draggingRef = useRef(false)
  const dockRef = useRef<HTMLElement | null>(null)

  const persistHeight = useCallback(
    (next: number) => {
      const clamped = Math.min(
        maxHeightPx(reserveForHitl),
        Math.max(minHeightPx(), next),
      )
      setHeight(clamped)
      try {
        localStorage.setItem(HEIGHT_KEY, String(clamped))
      } catch {
        /* ignore quota errors */
      }
    },
    [reserveForHitl],
  )

  useEffect(() => {
    function onMove(event: PointerEvent) {
      if (!draggingRef.current || !dockRef.current) return
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

  useEffect(() => {
    // 打开时按工坊高度回夹；HITL 时强制落到安全默认高度，避免旧 localStorage 盖住确认卡
    if (!open) return
    const ceiling = maxHeightPx(reserveForHitl)
    const target = reserveForHitl
      ? Math.min(height, defaultHeightPx(true), ceiling)
      : Math.min(height, ceiling)
    if (target < height) persistHeight(target)
  }, [open, reserveForHitl, height, persistHeight])

  const latest = items[0]
  const errorCount = items.filter((i) => i.tone === 'err').length

  return (
    <section
      ref={dockRef}
      className={cn(
        'gf-forge-log-dock',
        reserveForHitl && open && 'gf-forge-log-dock--hitl-safe',
      )}
      aria-label={t('eventLog')}
    >
      {open ? (
        <div
          role="separator"
          aria-orientation="horizontal"
          aria-label={t('forgeDragToResize')}
          tabIndex={0}
          className="gf-forge-dock-handle"
          onPointerDown={(event) => {
            draggingRef.current = true
            document.body.classList.add('gf-forge-dock-resizing')
            event.currentTarget.setPointerCapture(event.pointerId)
          }}
        />
      ) : null}

      <button
        type="button"
        onClick={onToggle}
        className="gf-interactive gf-forge-log-dock-header flex w-full cursor-pointer items-center justify-between gap-2 text-left transition hover:bg-black/[0.02]"
        aria-expanded={open}
      >
        <span className="gf-page-body flex min-w-0 items-center gap-2 text-sm font-medium">
          {open ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronUp className="h-4 w-4 shrink-0" />}
          <span className="truncate">{t('eventLog')}</span>
        </span>
        <span className="flex shrink-0 items-center gap-3">
          {!open && latest ? (
            <span className="gf-page-muted max-w-[14rem] truncate text-[11px] sm:max-w-[20rem]">
              {latest.label}
            </span>
          ) : null}
          {errorCount > 0 ? (
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
          {showGrid ? (
            <div className="gf-forge-log-dock-scroll">
              <StageLogGrid runPhase={runPhase} stages={stages} items={items} />
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
