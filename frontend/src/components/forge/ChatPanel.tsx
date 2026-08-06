import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'

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
  placeholder?: string
}

export function ChatPanel({
  messages,
  input,
  onInputChange,
  onSend,
  disabled,
  placeholder = '描述玩法、约束或迭代方向…',
}: Props) {
  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#12151a]">
      <header className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
        <div>
          <p className="font-mono text-[10px] tracking-[0.16em] text-white/40 uppercase">Chat</p>
          <p className="text-sm text-white/80">需求对话</p>
        </div>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-3 py-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              'max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
              m.role === 'user' && 'ml-auto bg-teal-500/15 text-teal-50 ring-1 ring-teal-400/25',
              m.role === 'assistant' && 'mr-auto bg-white/[0.05] text-white/85 ring-1 ring-white/[0.06]',
              m.role === 'system' &&
                'mx-auto max-w-full bg-amber-500/10 text-center font-mono text-[11px] text-amber-100/90 ring-1 ring-amber-400/20',
            )}
          >
            {m.content}
          </div>
        ))}
      </div>

      <div className="border-t border-white/[0.06] p-3">
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
          className="w-full resize-none rounded-xl border border-white/[0.08] bg-black/30 px-3 py-2.5 text-sm text-white/90 outline-none placeholder:text-white/30 focus-visible:ring-2 focus-visible:ring-teal-400/30 disabled:opacity-50"
          placeholder={placeholder}
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="font-mono text-[10px] text-white/30">⌘/Ctrl + Enter</span>
          <Button
            variant="primary"
            className="!rounded-lg !bg-teal-400 !px-4 !py-2 !text-black hover:!bg-teal-300"
            disabled={disabled || !input.trim()}
            onClick={onSend}
          >
            <Send className="h-3.5 w-3.5" />
            发送
          </Button>
        </div>
      </div>
    </section>
  )
}
