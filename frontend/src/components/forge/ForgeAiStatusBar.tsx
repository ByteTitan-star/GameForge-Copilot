import { Hexagon, Sparkles } from 'lucide-react'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Props = {
  busy: boolean
  className?: string
}

export function ForgeAiStatusBar({ busy, className }: Props) {
  const t = useT()

  return (
    <div
      className={cn(
        'gf-forge-ai-bar flex shrink-0 items-center gap-3 border-b',
        className,
      )}
    >
      <span className="relative grid h-9 w-9 place-items-center rounded-xl bg-[rgba(var(--gf-primary-rgb),0.08)] ring-1 ring-[rgba(var(--gf-primary-rgb),0.15)]">
        <Hexagon className="gf-text-accent h-5 w-5" strokeWidth={1.5} />
        <span
          className={cn(
            'absolute -right-0.5 -bottom-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-[var(--gf-surface)]',
            busy ? 'animate-pulse bg-amber-400' : 'bg-emerald-500',
          )}
          aria-hidden
        />
      </span>
      <p className="min-w-0 flex-1 text-sm font-medium text-[var(--gf-text)]">
        {busy ? t('forgeAiBuilding') : t('forgeAiReady')}
      </p>
      <Sparkles className="gf-text-accent h-4 w-4 shrink-0 opacity-80" aria-hidden />
    </div>
  )
}
