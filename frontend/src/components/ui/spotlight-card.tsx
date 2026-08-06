import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { usePointerStyle } from '@/hooks/use-pointer-style'

type Props = HTMLAttributes<HTMLElement> & {
  children: ReactNode
  as?: 'div' | 'article' | 'section'
  tone?: 'dark' | 'light'
}

export function SpotlightCard({
  children,
  className,
  as: Tag = 'div',
  tone = 'dark',
  ...rest
}: Props) {
  const { ref, style, onPointerMove, onPointerLeave } = usePointerStyle(5)

  return (
    <Tag
      ref={ref as never}
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
      style={style}
      className={cn(
        'group relative overflow-hidden rounded-3xl transition-[transform,box-shadow] duration-300 ease-out will-change-transform',
        tone === 'dark'
          ? 'border border-white/10 bg-white/[0.04] shadow-[0_20px_60px_rgba(0,0,0,0.35)]'
          : 'border border-black/[0.06] bg-white shadow-[0_16px_40px_rgba(15,23,42,0.08)] hover:shadow-[0_22px_50px_rgba(15,23,42,0.12)]',
        className,
      )}
      {...rest}
    >
      <div
        aria-hidden
        className={cn(
          'pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100',
          tone === 'dark'
            ? 'bg-[radial-gradient(500px_circle_at_var(--spot-x,50%)_var(--spot-y,40%),rgba(52,211,153,0.16),transparent_55%)]'
            : 'bg-[radial-gradient(420px_circle_at_var(--spot-x,50%)_var(--spot-y,40%),rgba(245,158,11,0.14),transparent_55%)]',
        )}
      />
      <div className="relative z-[1]">{children}</div>
    </Tag>
  )
}
