import { type KeyboardEvent, type ReactNode, useCallback, useEffect, useId, useRef } from 'react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { btnDangerSolid } from './buttonStyles'

/**
 * 后台确认对话框。外壳 token 驱动（gf-glass + admin 作用域柔阴影）；
 * 非危险确认走主题实心按钮（.gf-btn-primary 在 admin 内已被覆盖为实心品牌色），
 * 危险确认走 btnDangerSolid（实心红，比列表里的次级浅红更显眼，保留「这次真的执行」的升级感）。
 *
 * 可访问性（a11y）：
 * - Escape 关闭；打开时聚焦「取消」按钮（更安全的默认，避免误回车执行破坏性操作）；
 *   关闭后还原焦点到打开前的 activeElement。
 * - Tab/Shift+Tab 在弹窗内循环（手写焦点陷阱，不引库）。
 * - aria-modal + aria-labelledby 关联标题；背景容器不在此组件内 inert（由调用方决定），
 *   但焦点陷阱保证键盘不会逃逸到背景。
 */
export function ConfirmModal({
  title,
  children,
  onClose,
  onConfirm,
  confirmLabel,
  confirmDisabled,
  danger,
}: {
  title: string
  children: ReactNode
  onClose: () => void
  onConfirm: () => void
  confirmLabel: string
  confirmDisabled?: boolean
  danger?: boolean
}) {
  const t = useT()
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)

  // 打开时聚焦取消按钮（安全默认）；关闭时还原焦点。仅挂载/卸载时各跑一次。
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null
    // 下一帧聚焦，确保按钮已挂载
    const id = window.requestAnimationFrame(() => cancelRef.current?.focus())
    return () => {
      window.cancelAnimationFrame(id)
      // 还原焦点；若原元素已不在 DOM，忽略
      if (previouslyFocused && document.contains(previouslyFocused)) {
        previouslyFocused.focus()
      }
    }
  }, [])

  // Escape 关闭
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // Tab 焦点陷阱：在面板内首末可聚焦元素间循环
  const handleTab = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'Tab') return
    const panel = panelRef.current
    if (!panel) return
    const focusable = panel.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onKeyDown={handleTab}
    >
      <div ref={panelRef} className="gf-admin-card gf-admin-card-hover w-full max-w-md space-y-4 p-5 shadow-2xl">
        <h3 id={titleId} className="text-base text-[var(--gf-text)]">
          {title}
        </h3>
        {children}
        <div className="flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onClose}
            className="gf-interactive gf-chip inline-flex h-9 cursor-pointer items-center justify-center rounded-lg px-4 text-sm transition-colors hover:text-[var(--gf-text)]"
          >
            {t('cancel')}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={confirmDisabled}
            className={cn(
              danger ? btnDangerSolid : 'gf-interactive gf-btn-primary inline-flex h-9 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50',
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
