import { useCallback, useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

const STORAGE_KEY = 'gf-forge-stage-ratio'
const DEFAULT_STAGE_RATIO = 0.34
const MIN_STAGE_RATIO = 0.24
const MAX_STAGE_RATIO = 0.52
const MIN_LEFT_PX = 340

type Props = {
  stageOpen: boolean
  left: ReactNode
  right: ReactNode
  className?: string
}

function readStoredRatio(): number {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_STAGE_RATIO
    const n = Number(raw)
    if (!Number.isFinite(n)) return DEFAULT_STAGE_RATIO
    return Math.min(MAX_STAGE_RATIO, Math.max(MIN_STAGE_RATIO, n))
  } catch {
    return DEFAULT_STAGE_RATIO
  }
}

export function ForgeSplitLayout({ stageOpen, left, right, className }: Props) {
  const t = useT()
  const containerRef = useRef<HTMLDivElement>(null)
  const [stageRatio, setStageRatio] = useState(readStoredRatio)
  const draggingRef = useRef(false)

  const persistRatio = useCallback((ratio: number) => {
    const clamped = Math.min(MAX_STAGE_RATIO, Math.max(MIN_STAGE_RATIO, ratio))
    setStageRatio(clamped)
    try {
      localStorage.setItem(STORAGE_KEY, String(clamped))
    } catch {
      /* ignore quota errors */
    }
  }, [])

  useEffect(() => {
    if (!stageOpen) return

    function onPointerMove(event: PointerEvent) {
      if (!draggingRef.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const usable = rect.width - 8
      if (usable <= 0) return
      const leftWidth = event.clientX - rect.left
      const leftRatio = leftWidth / usable
      const nextStageRatio = 1 - leftRatio
      if (leftWidth < MIN_LEFT_PX) return
      persistRatio(nextStageRatio)
    }

    function onPointerUp() {
      draggingRef.current = false
      document.body.classList.remove('gf-forge-resizing')
    }

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      document.body.classList.remove('gf-forge-resizing')
    }
  }, [persistRatio, stageOpen])

  const leftRatio = `${((1 - stageRatio) * 100).toFixed(2)}%`

  return (
    <div
      ref={containerRef}
      className={cn(
        'gf-forge-split',
        stageOpen && 'gf-forge-split--stage-open',
        className,
      )}
      style={
        stageOpen
          ? ({ '--gf-forge-left-ratio': leftRatio } as CSSProperties)
          : undefined
      }
    >
      <div className="gf-forge-panel-left min-h-0">{left}</div>

      {stageOpen ? (
        <>
          <div
            role="separator"
            aria-orientation="vertical"
            aria-valuenow={Math.round(stageRatio * 100)}
            tabIndex={0}
            aria-label={t('forgeDragToResize')}
            title={t('forgeDragToResize')}
            className="gf-forge-split-handle"
            onPointerDown={(event) => {
              event.preventDefault()
              draggingRef.current = true
              document.body.classList.add('gf-forge-resizing')
            }}
          />
          <div className="gf-forge-panel-right min-h-0">{right}</div>
        </>
      ) : null}
    </div>
  )
}
