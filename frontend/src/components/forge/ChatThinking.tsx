import { Bot, ChevronRight, Loader2 } from 'lucide-react'
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

  if (live) {
    return (
      <div
        className="mr-auto flex max-w-[min(42rem,85%)] items-start gap-2.5 text-sm leading-relaxed"
        data-chat-row
      >
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[rgba(var(--gf-primary-rgb),0.16)] bg-[rgba(var(--gf-primary-rgb),0.08)] gf-text-accent">
          <Bot className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
        <div
          role="status"
          className="min-w-0 flex-1 rounded-2xl rounded-tl-md bg-black/[0.04] px-3.5 py-3 gf-page-body ring-1 ring-[var(--gf-border)]"
        >
          <p className="flex items-center gap-2 text-sm font-medium">
            <Loader2
              className="h-4 w-4 shrink-0 animate-spin motion-reduce:animate-none"
              aria-hidden
            />
            {t('thinkingLive')}
          </p>
          {items.map((item) => (
            <p key={item.id} className="mt-1.5 text-sm leading-relaxed">
              {item.content}
            </p>
          ))}
          <div
            data-testid="thinking-skeleton"
            className="mt-3 space-y-2"
            aria-hidden
          >
            <div className="h-2.5 w-[88%] animate-pulse rounded bg-black/[0.07] motion-reduce:animate-none" />
            <div className="h-2.5 w-[64%] animate-pulse rounded bg-black/[0.07] motion-reduce:animate-none" />
            <div className="h-2.5 w-[76%] animate-pulse rounded bg-black/[0.07] motion-reduce:animate-none" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mr-auto w-full max-w-[min(42rem,85%)]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="gf-interactive inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-lg px-1.5 text-[13px] gf-page-muted hover:bg-black/[0.04]"
        aria-expanded={open}
      >
        <ChevronRight
          className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-90')}
          aria-hidden
        />
        {t('thinkingDone')}
      </button>
      {open ? (
        <ol className="mt-1 space-y-1 border-l border-[var(--gf-border)] pl-3">
          {items.map((item) => (
            <li key={item.id} className="text-[13px] leading-relaxed gf-page-muted">
              {item.content}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  )
}
