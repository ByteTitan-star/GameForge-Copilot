import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import type { HitlWaitPayload } from '@/api/ws-types'
import { Button } from '@/components/ui/button'
import {
  isFailureHitlNode,
  parseDesignDoc,
  parseHitlFailure,
  type ParsedDesignDoc,
} from '@/lib/hitl-design-doc'
import { useT } from '@/i18n/use-t'

type Props = {
  payload: HitlWaitPayload
  onApprove: (doc: HitlWaitPayload['design_doc'], modifyText?: string | null) => void
  onReject: () => void
  busy?: boolean
}

export function HitlCard({ payload, onApprove, onReject, busy }: Props) {
  const t = useT()
  const parsed = useMemo(
    () => parseDesignDoc(payload.design_doc, typeof payload.design_doc === 'object' && payload.design_doc && 'title' in payload.design_doc ? String((payload.design_doc as { title?: string }).title ?? '') : ''),
    [payload.design_doc],
  )
  const failure = useMemo(
    () => parseHitlFailure(payload as unknown as Record<string, unknown>),
    [payload],
  )
  const isFailure = isFailureHitlNode(payload.node)

  const [gameplay, setGameplay] = useState(parsed.gameplay)
  const [controls, setControls] = useState(parsed.controls)
  const [modifyFeedback, setModifyFeedback] = useState('')

  useEffect(() => {
    setGameplay(parsed.gameplay)
    setControls(parsed.controls)
  }, [parsed.gameplay, parsed.controls])

  const failureTitle =
    payload.node === 'sandbox_failed' ? t('hitlSandboxFailed') : payload.node === 'qa_failed' ? t('hitlQaFailed') : t('manualReview')

  const errorLines = [...failure.errors, ...failure.issues]

  function buildDoc(): ParsedDesignDoc {
    return { ...parsed, gameplay, controls }
  }

  function handleApprove() {
    const doc = buildDoc()
    const modified =
      gameplay !== parsed.gameplay ||
      controls !== parsed.controls ||
      Boolean(modifyFeedback.trim())
    const modifyText = modified
      ? modifyFeedback.trim() ||
        `gameplay: ${gameplay}\ncontrols: ${controls}`
      : null
    onApprove(doc as HitlWaitPayload['design_doc'], modifyText)
  }

  return (
    <div className="rounded-2xl border border-[#d49d12]/30 bg-[#fff5d6] p-4 shadow-[0_0_40px_rgba(212,157,18,0.12)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] tracking-[0.16em] text-[#a77b10] uppercase">
            {isFailure ? failureTitle : t('manualReview')}
          </p>
          <h3 className="mt-1 text-base text-[#5f4811]">
            {t('confirmDesign')} · {parsed.title || payload.node}
          </h3>
          <p className="mt-1 text-xs text-[#8a6b21]">
            {isFailure ? t('hitlSuggestedActions') : t('continueAfterApproval')}
          </p>
        </div>
        {isFailure ? <AlertTriangle className="h-5 w-5 shrink-0 text-[#c4840f]" aria-hidden /> : null}
      </div>

      {isFailure && errorLines.length > 0 ? (
        <div className="mt-4 rounded-xl border border-rose-300/40 bg-rose-50/80 px-3 py-2">
          <p className="font-mono text-[10px] text-rose-700 uppercase">{t('hitlErrorList')}</p>
          <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-sm text-rose-900">
            {errorLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {failure.retries != null ? (
            <p className="mt-2 text-[11px] text-rose-700/80">retries: {failure.retries}</p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        <label className="block space-y-1.5">
          <span className="font-mono text-[10px] text-[#a17f31] uppercase">{t('gameplay')}</span>
          <textarea
            value={gameplay}
            onChange={(e) => setGameplay(e.target.value)}
            rows={isFailure ? 4 : 3}
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
        {parsed.levels.length > 0 ? (
          <div>
            <p className="font-mono text-[10px] text-[#a17f31] uppercase">{t('levels')}</p>
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {parsed.levels.map((lv) => (
                <li
                  key={lv}
                  className="rounded-md bg-white/60 px-2 py-1 font-mono text-[11px] text-[#7f631c] ring-1 ring-[#d49d12]/20"
                >
                  {lv}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <label className="block space-y-1.5">
          <span className="font-mono text-[10px] text-[#a17f31] uppercase">{t('hitlModifyFeedback')}</span>
          <textarea
            value={modifyFeedback}
            onChange={(e) => setModifyFeedback(e.target.value)}
            rows={2}
            placeholder={t('describeIteration')}
            className="w-full resize-none rounded-xl border border-[#d49d12]/20 bg-white/70 px-3 py-2 text-sm text-[#5f4811] outline-none focus-visible:ring-2 focus-visible:ring-[#d49d12]/30"
          />
        </label>
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
          onClick={handleApprove}
        >
          {t('approveAndContinue')}
        </Button>
      </div>
    </div>
  )
}
