import { useState } from 'react'
import type { HitlWaitPayload } from '@/api/types.gen'
import { Button } from '@/components/ui/button'

type Props = {
  payload: HitlWaitPayload
  onApprove: (doc: HitlWaitPayload['design_doc']) => void
  onReject: () => void
  busy?: boolean
}

export function HitlCard({ payload, onApprove, onReject, busy }: Props) {
  const [gameplay, setGameplay] = useState(payload.design_doc.gameplay)
  const [controls, setControls] = useState(payload.design_doc.controls)

  return (
    <div className="rounded-2xl border border-amber-400/30 bg-amber-500/[0.08] p-4 shadow-[0_0_40px_rgba(251,191,36,0.08)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] tracking-[0.16em] text-amber-200/70 uppercase">HITL</p>
          <h3 className="mt-1 text-base text-amber-50">确认策划稿 · {payload.design_doc.title}</h3>
          <p className="mt-1 text-xs text-amber-100/60">节点 {payload.node} — 批准后继续 art → code → qa</p>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        <label className="block space-y-1.5">
          <span className="font-mono text-[10px] text-amber-100/50 uppercase">Gameplay</span>
          <textarea
            value={gameplay}
            onChange={(e) => setGameplay(e.target.value)}
            rows={3}
            className="w-full resize-none rounded-xl border border-amber-200/15 bg-black/30 px-3 py-2 text-sm text-amber-50 outline-none focus-visible:ring-2 focus-visible:ring-amber-300/30"
          />
        </label>
        <label className="block space-y-1.5">
          <span className="font-mono text-[10px] text-amber-100/50 uppercase">Controls</span>
          <textarea
            value={controls}
            onChange={(e) => setControls(e.target.value)}
            rows={2}
            className="w-full resize-none rounded-xl border border-amber-200/15 bg-black/30 px-3 py-2 text-sm text-amber-50 outline-none focus-visible:ring-2 focus-visible:ring-amber-300/30"
          />
        </label>
        <div>
          <p className="font-mono text-[10px] text-amber-100/50 uppercase">Levels</p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {payload.design_doc.levels.map((lv) => (
              <li
                key={lv}
                className="rounded-md bg-black/25 px-2 py-1 font-mono text-[11px] text-amber-100/80 ring-1 ring-amber-200/15"
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
          className="!rounded-lg !px-3 !py-2 text-amber-100/70 hover:bg-white/5"
          disabled={busy}
          onClick={onReject}
        >
          驳回并停止
        </Button>
        <Button
          className="!rounded-lg !bg-amber-300 !px-4 !py-2 !text-black hover:!bg-amber-200"
          disabled={busy}
          onClick={() =>
            onApprove({
              ...payload.design_doc,
              gameplay,
              controls,
            })
          }
        >
          批准继续
        </Button>
      </div>
    </div>
  )
}
