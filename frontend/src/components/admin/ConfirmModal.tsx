import { type ReactNode } from 'react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import { btnDangerSolid } from './buttonStyles'

/**
 * 后台确认对话框。外壳 token 驱动（gf-glass + admin 作用域柔阴影）；
 * 非危险确认走主题实心按钮（.gf-btn-primary 在 admin 内已被覆盖为实心品牌色），
 * 危险确认走 btnDangerSolid（实心红，比列表里的次级浅红更显眼，保留「这次真的执行」的升级感）。
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
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
    >
      <div className="gf-admin-card gf-admin-card-hover w-full max-w-md space-y-4 p-5 shadow-2xl">
        <h3 className="text-base text-[var(--gf-text)]">{title}</h3>
        {children}
        <div className="flex justify-end gap-2">
          <button
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

