import { type ReactNode } from 'react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

/**
 * 后台确认对话框。token 驱动外壳（gf-glass），确认按钮非危险走 gf-btn-primary，
 * 危险操作用语义红（红 = 通用破坏性语义，跨主题保留）。
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
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="gf-glass w-full max-w-md space-y-4 rounded-2xl p-5 shadow-2xl">
        <h3 className="text-base text-[var(--gf-text)]">{title}</h3>
        {children}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="gf-interactive gf-chip cursor-pointer rounded-lg px-3 py-2 text-sm hover:text-[var(--gf-text)]"
          >
            {t('cancel')}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={confirmDisabled}
            className={cn(
              'gf-interactive inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition disabled:cursor-not-allowed disabled:opacity-50',
              danger ? 'bg-red-500 hover:bg-red-600' : 'gf-btn-primary',
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
