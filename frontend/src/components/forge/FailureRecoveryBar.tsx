import { Loader2, Mail, MessageSquare, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Props = {
  runId: string
  errorSummary?: string
  onRevise: () => void
  onRetry: () => void
  busy?: boolean
  className?: string
}

export function FailureRecoveryBar({
  runId,
  errorSummary,
  onRevise,
  onRetry,
  busy,
  className,
}: Props) {
  const t = useT()
  const supportEmail = import.meta.env.VITE_SUPPORT_EMAIL ?? 'support@gameforge.local'

  async function copyRunId() {
    try {
      await navigator.clipboard.writeText(runId)
    } catch {
      /* ignore */
    }
  }

  function contactAdmin() {
    void copyRunId()
    const subject = encodeURIComponent(`GameForge run ${runId}`)
    const body = encodeURIComponent(
      `${errorSummary ? `Error: ${errorSummary}\n\n` : ''}run_id: ${runId}`,
    )
    window.location.href = `mailto:${supportEmail}?subject=${subject}&body=${body}`
  }

  return (
    <section
      className={cn(
        'rounded-xl border border-rose-300/40 bg-rose-50/90 px-3 py-3 text-rose-950',
        className,
      )}
      role="alert"
    >
      <p className="text-sm font-medium">{t('failureRecoveryTitle')}</p>
      {errorSummary ? <p className="mt-1 text-xs opacity-85">{errorSummary}</p> : null}
      <p className="mt-1 font-mono text-[10px] opacity-60">{runId}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="ghost"
          className="!h-8 !rounded-lg !px-2.5 !text-xs !text-rose-900 hover:!bg-rose-100"
          disabled={busy}
          onClick={onRevise}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          {t('failureRevise')}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="!h-8 !rounded-lg !px-2.5 !text-xs !text-rose-900 hover:!bg-rose-100"
          disabled={busy}
          onClick={onRetry}
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
          {t('failureRetry')}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="!h-8 !rounded-lg !px-2.5 !text-xs !text-rose-900 hover:!bg-rose-100"
          onClick={contactAdmin}
        >
          <Mail className="h-3.5 w-3.5" />
          {t('failureContact')}
        </Button>
      </div>
    </section>
  )
}
