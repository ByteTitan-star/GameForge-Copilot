import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'

type Props = {
  open: boolean
  gameTitle: string
  defaultNote?: string
  busy?: boolean
  onCancel: () => void
  onConfirm: (note: string) => void
}

export function PublishNoteModal({
  open,
  gameTitle,
  defaultNote = '',
  busy,
  onCancel,
  onConfirm,
}: Props) {
  const [note, setNote] = useState(defaultNote)

  useEffect(() => {
    if (open) setNote(defaultNote)
  }, [open, defaultNote])

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
            className="relative w-full max-w-md rounded-2xl border border-white/[0.08] bg-[#131821]/95 p-5 shadow-[0_0_40px_rgba(34,211,238,0.12)]"
          >
            <p className="font-mono text-[10px] tracking-[0.16em] text-cyan-300/70 uppercase">Publish</p>
            <h3 className="mt-2 text-lg text-white">提交发布审批</h3>
            <p className="mt-1 text-sm text-white/50">「{gameTitle}」将进入管理员审批队列。</p>
            <label className="mt-4 block space-y-1.5 text-sm">
              <span className="text-white/45">发布说明（可选）</span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                maxLength={500}
                placeholder="玩法亮点、目标受众、测试说明…"
                className="w-full resize-none rounded-xl border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none placeholder:text-white/30 focus:border-cyan-400/40 focus:ring-2 focus:ring-cyan-400/15"
              />
            </label>
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
                onClick={() => onConfirm(note.trim())}
                className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-cyan-400 px-3 py-2 text-sm font-medium text-black hover:bg-cyan-300 disabled:opacity-60"
              >
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                提交
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
