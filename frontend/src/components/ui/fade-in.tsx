import { useEffect, useState, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

type Props = {
  children: ReactNode
  delayMs?: number
  durationMs?: number
  className?: string
}

export function FadeIn({ children, delayMs = 0, durationMs = 700, className }: Props) {
  const [show, setShow] = useState(false)
  useEffect(() => {
    const t = window.setTimeout(() => setShow(true), delayMs)
    return () => window.clearTimeout(t)
  }, [delayMs])

  return (
    <div
      className={cn('transition-opacity', className)}
      style={{
        opacity: show ? 1 : 0,
        transitionDuration: `${durationMs}ms`,
      }}
    >
      {children}
    </div>
  )
}
