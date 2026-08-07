import { GameStatus } from '@/api/enums'
import { cn } from '@/lib/cn'

type Props = { status: GameStatus; className?: string }

const label: Record<GameStatus, string> = {
  [GameStatus.draft]: 'Draft',
  [GameStatus.submitted]: 'Pending',
  [GameStatus.reviewing]: 'Pending',
  [GameStatus.published]: 'Published',
  [GameStatus.rejected]: 'Rejected',
  [GameStatus.taken_down]: 'Taken down',
}

export function StatusBadge({ status, className }: Props) {
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
      {label[status]}
    </span>
  )
}
