import { cn } from '@/lib/cn'

type Props = {
  src: string
  title?: string
  variant?: 'light' | 'console'
  className?: string
}

/** 试玩容器：sandbox 不含 allow-same-origin（对齐 docs/08） */
export function GamePlayer({
  src,
  title = 'Game preview',
  variant = 'light',
  className,
}: Props) {
  const console = variant === 'console'
  return (
    <div
      className={cn(
        'overflow-hidden',
        console
          ? 'h-full rounded-xl border border-white/[0.08] bg-black/40'
          : 'rounded-2xl border border-[rgba(30,50,90,0.1)] bg-white shadow-sm',
        className,
      )}
    >
      <div
        className={cn(
          'border-b px-4 py-2 text-xs',
          console
            ? 'border-white/[0.06] font-mono text-white/45'
            : 'border-[rgba(30,50,90,0.08)] text-[rgba(30,50,90,0.55)]',
        )}
      >
        {title}
      </div>
      <iframe
        title={title}
        src={src}
        sandbox="allow-scripts"
        className={cn('w-full bg-[#111]', console ? 'h-[calc(100%-2.25rem)] min-h-[280px]' : 'h-[70vh]')}
      />
    </div>
  )
}
