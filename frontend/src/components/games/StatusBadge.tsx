import { GameStatus } from '@/api/enums'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'
import type { MessageKey } from '@/i18n/messages'

type Props = { status: GameStatus; className?: string }

const statusKey: Record<GameStatus, MessageKey> = {
  [GameStatus.draft]: 'statusDraft',
  [GameStatus.submitted]: 'statusPending',
  [GameStatus.reviewing]: 'statusPending',
  [GameStatus.published]: 'statusPublished',
  [GameStatus.rejected]: 'statusRejected',
  [GameStatus.taken_down]: 'statusTakenDown',
}

export function StatusBadge({ status, className }: Props) {
  const t = useT()
  const pending = status === GameStatus.submitted || status === GameStatus.reviewing
  const published = status === GameStatus.published
  const rejected = status === GameStatus.rejected || status === GameStatus.taken_down
  const draft = status === GameStatus.draft

  return (
    <span
      className={cn(
        'relative inline-flex overflow-hidden rounded-md px-2 py-0.5 font-mono text-[10px] tracking-[0.14em] uppercase',
        draft && 'status-draft bg-[#3B4252] text-white/80',
        pending && 'status-pending bg-[#F59E0B]/20 text-[#FBBF24]',
        published && 'status-published bg-cyan-400/15 text-[#22D3EE]',
        rejected && 'status-rejected bg-rose-500/20 text-[#F43F5E]',
        className,
      )}
    >
      {t(statusKey[status])}
    </span>
  )
}
