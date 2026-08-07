import { AnimatePresence, motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'

type Props = {
  open: boolean
  title: string
  busy?: boolean
  onCancel: () => void
  onConfirm: () => void
}

export function DeleteConfirmModal({ open, title, busy, onCancel, onConfirm }: Props) {
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
            aria-label="关闭"
            className="absolute inset-0 cursor-pointer bg-black/55 backdrop-blur-md"
            onClick={onCancel}
          />
          <motion.div
            role="dialog"
            aria-modal
            initial={{ opacity: 0, scale: 0.92, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="relative w-full max-w-sm rounded-2xl border border-white/[0.08] bg-[#131821]/95 p-5 shadow-[0_0_40px_rgba(244,63,94,0.12)]"
          >
            <p className="font-mono text-[10px] tracking-[0.16em] text-rose-300/70 uppercase">Delete</p>
            <h3 className="mt-2 text-lg text-white">确认删除？</h3>
            <p className="mt-2 text-sm text-white/55">
              「{title}」删除后不可恢复。
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={onCancel}
                className="cursor-pointer rounded-lg px-3 py-2 text-sm text-white/60 hover:bg-white/[0.06]"
              >
                取消
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={onConfirm}
                className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-rose-500 px-3 py-2 text-sm font-medium text-white hover:bg-rose-400 disabled:opacity-60"
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                确认删除
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
