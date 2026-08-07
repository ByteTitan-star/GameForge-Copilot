import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronRight, Gamepad2, KeyRound, Sparkles, X } from 'lucide-react'
import type { MessageKey } from '@/i18n/messages'
import { TemplatePicker } from '@/components/forge/TemplatePicker'
import type { GameTemplate } from '@/api/templates'
import { markOnboardingDone } from '@/lib/onboarding-storage'
import { useT } from '@/i18n/use-t'

type Props = {
  open: boolean
  onClose: () => void
}

const STEPS = ['play', 'llm', 'forge'] as const

const STEP_I18N: Record<(typeof STEPS)[number], { title: MessageKey; body: MessageKey }> = {
  play: { title: 'onboardingPlayTitle', body: 'onboardingPlayBody' },
  llm: { title: 'onboardingLlmTitle', body: 'onboardingLlmBody' },
  forge: { title: 'onboardingForgeTitle', body: 'onboardingForgeBody' },
}

export function OnboardingModal({ open, onClose }: Props) {
  const t = useT()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (open) setStep(0)
  }, [open])

  function finish() {
    markOnboardingDone()
    onClose()
  }

  function skip() {
    finish()
  }

  function next() {
    if (step >= STEPS.length - 1) finish()
    else setStep((s) => s + 1)
  }

  const icons = [Gamepad2, KeyRound, Sparkles]
  const Icon = icons[step] ?? Sparkles
  const stepKey = STEPS[step]

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/55 backdrop-blur-sm"
            aria-hidden
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="onboarding-title"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            className="fixed left-1/2 top-1/2 z-[101] w-[min(100%-2rem,480px)] max-h-[min(90vh,640px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-white/15 bg-[#12151a] p-6 shadow-2xl"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-xl bg-cyan-400/15 text-cyan-300">
                <Icon className="h-5 w-5" />
              </div>
              <button
                type="button"
                aria-label={t('close')}
                onClick={skip}
                className="grid h-9 w-9 cursor-pointer place-items-center rounded-lg text-white/45 transition hover:bg-white/10 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mt-4 font-mono text-[10px] tracking-[0.16em] text-white/40 uppercase">
              {t('onboardingStep').replace('{n}', String(step + 1)).replace('{total}', '3')}
            </p>
            <h2 id="onboarding-title" className="mt-1 text-xl font-medium text-white">
              {t(STEP_I18N[stepKey].title)}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-white/60">
              {t(STEP_I18N[stepKey].body)}
            </p>

            {stepKey === 'forge' ? (
              <div className="mt-4 rounded-xl border border-white/10 bg-black/30 p-3">
                <TemplatePicker
                  compact
                  onSelect={(tpl: GameTemplate) => {
                    finish()
                    navigate(`/forge?template=${encodeURIComponent(tpl.template_id)}`)
                  }}
                />
              </div>
            ) : null}

            <div className="mt-6 flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={skip}
                className="cursor-pointer rounded-lg px-3 py-2 text-xs text-white/45 transition hover:text-white/75"
              >
                {t('onboardingSkip')}
              </button>
              <div className="flex flex-wrap gap-2">
                {stepKey === 'play' ? (
                  <Link
                    to="/discover"
                    onClick={finish}
                    className="inline-flex items-center gap-1 rounded-lg border border-white/15 px-3 py-2 text-xs text-white/80"
                  >
                    {t('discover')}
                  </Link>
                ) : null}
                {stepKey === 'llm' ? (
                  <Link
                    to="/settings"
                    onClick={finish}
                    className="inline-flex items-center gap-1 rounded-lg border border-white/15 px-3 py-2 text-xs text-white/80"
                  >
                    {t('settings')}
                  </Link>
                ) : null}
                <button
                  type="button"
                  onClick={next}
                  className="inline-flex cursor-pointer items-center gap-1 rounded-lg bg-white px-4 py-2 text-xs font-medium text-black"
                >
                  {step >= STEPS.length - 1 ? t('onboardingDone') : t('onboardingNext')}
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </motion.div>
        </>
      ) : null}
    </AnimatePresence>
  )
}
