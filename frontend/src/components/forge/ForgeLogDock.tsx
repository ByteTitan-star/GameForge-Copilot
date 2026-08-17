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
const DEFAULT_HEIGHT = 240
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
 * 展开后顶部可垂直拖拽调整高度（120px ~ 45vh，持久化）。
 * 失败恢复条与阶段条固定在滚动区外；事件流 newest-first，默认钉住顶部跟随最新。
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
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const followLatestRef = useRef(true)

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

  // newest-first：靠近顶部视为跟随；用户上翻后暂停自动钉顶
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !open) return
    function onScroll() {
      followLatestRef.current = el.scrollTop < 24
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [open])

  useEffect(() => {
    if (!open || !followLatestRef.current) return
    const el = scrollRef.current
    if (el) el.scrollTop = 0
  }, [items, open])

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
          {showPipeline ? (
            <div className="gf-forge-log-dock-pipeline">
              <StagePipeline runPhase={runPhase} stages={stages} variant="bar" />
            </div>
          ) : null}
          <div ref={scrollRef} className="gf-forge-log-dock-scroll">
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
