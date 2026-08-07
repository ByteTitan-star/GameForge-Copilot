import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Palette, X } from 'lucide-react'
import { useT } from '@/i18n/use-t'
import { ThemePanel } from './ThemePanel'

type ThemePanelModalProps = {
  open: boolean
  onClose: () => void
}

export function ThemePanelModal({ open, onClose }: ThemePanelModalProps) {
  const t = useT()
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-end justify-center p-0 sm:items-center sm:p-4">
      <button
        type="button"
        className="absolute inset-0 cursor-pointer bg-black/60 backdrop-blur-sm"
        aria-label={t('themeClose')}
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="gf-theme-dialog-title"
        className="gf-glass relative z-10 flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl sm:rounded-2xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-white/[0.06] px-5 py-4">
          <div className="flex items-center gap-2">
            <Palette className="gf-text-accent h-5 w-5" />
            <h2 id="gf-theme-dialog-title" className="text-lg font-semibold text-white">
              {t('themeTitle')}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="gf-interactive grid h-9 w-9 cursor-pointer place-items-center rounded-lg text-white/50 transition hover:bg-white/[0.06] hover:text-white"
            aria-label={t('themeClose')}
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          <ThemePanel />
        </div>
      </div>
    </div>,
    document.body,
  )
}
