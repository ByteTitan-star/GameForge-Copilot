import { ChevronRight, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ChatMsg } from '@/components/forge/chat-blocks'
import { cn } from '@/lib/cn'
import { useT } from '@/i18n/use-t'

type Props = {
  items: ChatMsg[]
  live?: boolean
}

export function ChatThinking({ items, live = false }: Props) {
  const t = useT()
  const [open, setOpen] = useState(live)

  useEffect(() => {
    setOpen(live)
  }, [live])

  return (
    <div className="mx-auto w-full max-w-[94%]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="gf-interactive inline-flex min-h-8 cursor-pointer items-center gap-1.5 rounded-lg px-1.5 text-[12px] gf-page-muted hover:bg-black/[0.04]"
        aria-expanded={open}
      >
        {live ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
        ) : (
          <ChevronRight
            className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-90')}
            aria-hidden
          />
        )}
        {live ? t('thinkingLive') : t('thinkingDone')}
      </button>
      {open ? (
        <ol className="mt-1 space-y-1 border-l border-[var(--gf-border)] pl-3">
          {items.map((item) => (
            <li key={item.id} className="text-[12px] leading-relaxed gf-page-muted">
              {item.content}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  )
}
