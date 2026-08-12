import { AnimatePresence, motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'
import { useT } from '@/i18n/use-t'

type Tone = 'danger' | 'warn'

type Props = {
  open: boolean
  /** 顶部小标签文字（如 Delete / Unpublish / Withdraw） */
  badge: string
  /** 主标题（已本地化） */
  headline: string
  /** 正文（已本地化） */
  body: string
  confirmLabel: string
  tone?: Tone
  busy?: boolean
  onCancel: () => void
  onConfirm: () => void
}

const TONE_BADGE: Record<Tone, string> = {
  danger: 'text-rose-300/70',
  warn: 'text-amber-300/70',
}

const TONE_BTN: Record<Tone, string> = {
  danger: 'bg-rose-500 hover:bg-rose-400',
  warn: 'bg-amber-500 hover:bg-amber-400 text-black',
}

const TONE_GLOW: Record<Tone, string> = {
  danger: 'shadow-[0_0_40px_rgba(244,63,94,0.12)]',
  warn: 'shadow-[0_0_40px_rgba(245,158,11,0.12)]',
}

/** 通用确认弹窗：删除/下架/撤回共用。单个删除时传 title 占位渲染后的 headline/body。 */
export function DeleteConfirmModal({
  open,
  badge,
  headline,
  body,
  confirmLabel,
  tone = 'danger',
  busy,
  onCancel,
  onConfirm,
}: Props) {
  const t = useT()

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            type="button"
            aria-label={t('close')}
            className="absolute inset-0 cursor-pointer bg-black/55 backdrop-blur-md"
            onClick={onCancel}
          />
          <motion.div
            role="dialog"
            aria-modal
            initial={{ opacity: 0, scale: 0.92, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className={cn(
              'relative w-full max-w-sm rounded-2xl border border-white/[0.08] bg-[#131821]/95 p-5',
              TONE_GLOW[tone],
            )}
          >
            <p className={cn('font-mono text-[10px] tracking-[0.16em] uppercase', TONE_BADGE[tone])}>
              {badge}
            </p>
            <h3 className="mt-2 text-lg text-white">{headline}</h3>
            <p className="mt-2 text-sm text-white/55">{body}</p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={onCancel}
                className="cursor-pointer rounded-lg px-3 py-2 text-sm text-white/60 hover:bg-white/[0.06]"
              >
                {t('cancel')}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={onConfirm}
                className={cn(
                  'inline-flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white disabled:opacity-60',
                  TONE_BTN[tone],
                )}
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                {confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
