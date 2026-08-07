import { useState } from 'react'
import type { HitlWaitPayload } from '@/api/ws-types'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'

type Props = {
  payload: HitlWaitPayload
  onApprove: (doc: HitlWaitPayload['design_doc']) => void
  onReject: () => void
  busy?: boolean
}

export function HitlCard({ payload, onApprove, onReject, busy }: Props) {
  const t = useT()
  const [gameplay, setGameplay] = useState(payload.design_doc.gameplay)
  const [controls, setControls] = useState(payload.design_doc.controls)

  return (
    <div className="rounded-2xl border border-[#d49d12]/30 bg-[#fff5d6] p-4 shadow-[0_0_40px_rgba(212,157,18,0.12)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] tracking-[0.16em] text-[#a77b10] uppercase">{t('manualReview')}</p>
          <h3 className="mt-1 text-base text-[#5f4811]">{t('confirmDesign')} · {payload.design_doc.title}</h3>
          <p className="mt-1 text-xs text-[#8a6b21]">{t('continueAfterApproval')}</p>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        <label className="block space-y-1.5">
          <span className="font-mono text-[10px] text-[#a17f31] uppercase">{t('gameplay')}</span>
          <textarea
            value={gameplay}
            onChange={(e) => setGameplay(e.target.value)}
            rows={3}
            className="w-full resize-none rounded-xl border border-[#d49d12]/20 bg-white/70 px-3 py-2 text-sm text-[#5f4811] outline-none focus-visible:ring-2 focus-visible:ring-[#d49d12]/30"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="font-mono text-[10px] text-[#a17f31] uppercase">{t('controls')}</span>
          <textarea
            value={controls}
            onChange={(e) => setControls(e.target.value)}
            rows={2}
            className="w-full resize-none rounded-xl border border-[#d49d12]/20 bg-white/70 px-3 py-2 text-sm text-[#5f4811] outline-none focus-visible:ring-2 focus-visible:ring-[#d49d12]/30"
          />
        </label>
        <div>
          <p className="font-mono text-[10px] text-[#a17f31] uppercase">{t('levels')}</p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {payload.design_doc.levels.map((lv) => (
              <li
                key={lv}
                className="rounded-md bg-white/60 px-2 py-1 font-mono text-[11px] text-[#7f631c] ring-1 ring-[#d49d12]/20"
              >
                {lv}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button
          variant="ghost"
          className="!rounded-lg !px-3 !py-2 !text-[#8a6b21] hover:!bg-black/[0.05]"
          disabled={busy}
          onClick={onReject}
        >
          {t('rejectAndStop')}
        </Button>
        <Button
          className="!rounded-lg !bg-[#ffcf5a] !px-4 !py-2 !text-[#493607] hover:!bg-[#ffda7e]"
          disabled={busy}
          onClick={() =>
            onApprove({
              ...payload.design_doc,
              gameplay,
              controls,
            })
          }
        >
          {t('approveAndContinue')}
        </Button>
      </div>
    </div>
  )
}
