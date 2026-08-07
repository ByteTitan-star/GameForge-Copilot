import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'
import { useT } from '@/i18n/use-t'

export type ChatMsg = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
}

type Props = {
  messages: ChatMsg[]
  input: string
  onInputChange: (v: string) => void
  onSend: () => void
  disabled?: boolean
  /** 生成中：最后一条 assistant 显示闪烁光标，模拟流式增量 */
  streaming?: boolean
  placeholder?: string
  className?: string
  showComposer?: boolean
}

export function ChatPanel({
  messages,
  input,
  onInputChange,
  onSend,
  disabled,
  streaming,
  placeholder,
  className,
  showComposer = true,
}: Props) {
  const t = useT()
  const composerPlaceholder = placeholder ?? t('describeIteration')
  const lastAssistantId = [...messages].reverse().find((m) => m.role === 'assistant')?.id
  return (
    <section className={cn('flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-black/[0.08] bg-white', className)}>
      <header className="flex items-center justify-between border-b border-black/[0.07] px-4 py-3">
        <p className="text-sm font-medium text-[#20262d]">{t('requirementChat')}</p>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-3 py-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              'max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
              m.role === 'user' && 'ml-auto bg-[#5271ff]/12 text-[#3046a8] ring-1 ring-[#5271ff]/20',
              m.role === 'assistant' && 'mr-auto bg-[#eef1f3] text-[#303940] ring-1 ring-black/[0.05]',
              m.role === 'system' &&
                'mx-auto max-w-full bg-[#ffcf5a]/15 text-center font-mono text-[11px] text-[#785d14] ring-1 ring-[#d49d12]/20',
            )}
          >
            {m.content}
            {streaming && m.id === lastAssistantId ? (
              <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-[#5271ff]/70 align-middle" />
            ) : null}
          </div>
        ))}
      </div>

      {showComposer ? <div className="border-t border-black/[0.07] p-3">
        <textarea
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          rows={3}
          disabled={disabled}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              onSend()
            }
          }}
          className="w-full resize-none rounded-xl border border-black/[0.1] bg-[#f5f7f8] px-3 py-2.5 text-sm text-[#20262d] outline-none placeholder:text-[#9099a1] focus-visible:ring-2 focus-visible:ring-[#5271ff]/25 disabled:opacity-50"
          placeholder={composerPlaceholder}
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="font-mono text-[10px] text-[#9099a1]">⌘/Ctrl + Enter</span>
          <Button
            variant="primary"
            className="!rounded-lg !bg-[#20262d] !px-4 !py-2 !text-white hover:!bg-[#303940]"
            disabled={disabled || !input.trim()}
            onClick={onSend}
          >
            <Send className="h-3.5 w-3.5" />
            {t('sendRequirement')}
          </Button>
        </div>
      </div> : null}
    </section>
  )
}
