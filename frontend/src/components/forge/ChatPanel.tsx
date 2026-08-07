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
  streaming?: boolean
  placeholder?: string
  className?: string
  showComposer?: boolean
  /** workshop = 浅色工坊；forge-hero = Forge Hero 内嵌；light = 旧版 forge 白底 */
  variant?: 'light' | 'workshop' | 'forge-hero'
  /** document = 由外层容器滚动；panel = 消息区内部滚动 */
  scrollMode?: 'panel' | 'document'
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
  variant = 'light',
  scrollMode = 'panel',
}: Props) {
  const t = useT()
  const workshop = variant === 'workshop' || variant === 'forge-hero'
  const hero = variant === 'forge-hero'
  const documentScroll = hero && scrollMode === 'document'
  const composerPlaceholder = placeholder ?? t('describeIteration')
  const lastAssistantId = [...messages].reverse().find((m) => m.role === 'assistant')?.id
  return (
    <section
      className={cn(
        'flex flex-col',
        documentScroll ? 'min-h-0' : 'h-full min-h-0 overflow-hidden',
        hero
          ? 'bg-transparent'
          : cn(
              'rounded-2xl border',
              workshop
                ? 'gf-border-subtle gf-glass border bg-[var(--gf-surface)]'
                : 'border-black/[0.08] bg-white',
            ),
        className,
      )}
    >
      {!hero ? (
        <header className="gf-border-subtle flex items-center justify-between border-b px-4 py-3">
          <p className={cn('text-sm font-medium', workshop ? 'gf-page-body' : 'text-[#20262d]')}>
            {t('requirementChat')}
          </p>
        </header>
      ) : null}

      <div
        className={cn(
          'space-y-3 px-4 py-4 md:px-5',
          documentScroll ? 'shrink-0' : 'min-h-0 flex-1 overflow-y-auto',
        )}
      >
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              'max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
              m.role === 'user' &&
                (workshop
                  ? 'ml-auto gf-bg-accent-soft gf-page-body gf-ring-accent'
                  : 'ml-auto bg-[#5271ff]/12 text-[#3046a8] ring-1 ring-[#5271ff]/20'),
              m.role === 'assistant' &&
                (workshop
                  ? 'mr-auto bg-black/[0.03] gf-page-body ring-1 ring-[var(--gf-border)]'
                  : 'mr-auto bg-[#eef1f3] text-[#303940] ring-1 ring-black/[0.05]'),
              m.role === 'system' &&
                (workshop
                  ? 'mx-auto max-w-full bg-amber-50 text-center font-mono text-[11px] text-amber-900 ring-1 ring-amber-200'
                  : 'mx-auto max-w-full bg-[#ffcf5a]/15 text-center font-mono text-[11px] text-[#785d14] ring-1 ring-[#d49d12]/20'),
            )}
          >
            {m.content}
            {streaming && m.id === lastAssistantId ? (
              <span
                className={cn(
                  'ml-0.5 inline-block h-3.5 w-1.5 animate-pulse align-middle',
                  workshop ? 'bg-[var(--gf-primary)] opacity-70' : 'bg-[#5271ff]/70',
                )}
              />
            ) : null}
          </div>
        ))}
      </div>

      {showComposer ? (
        <div className={cn(hero ? 'shrink-0 p-4 pt-2 md:px-5' : 'gf-border-subtle border-t p-3')}>
          <div className={cn(hero && 'gf-forge-composer-wrap')}>
            <textarea
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              rows={hero ? 3 : 3}
              disabled={disabled}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  onSend()
                }
              }}
              className={cn(
                'w-full resize-none px-3 py-2.5 text-sm outline-none disabled:opacity-50',
                hero
                  ? 'gf-page-body placeholder:text-[var(--gf-text-muted)]'
                  : cn(
                      'rounded-xl border',
                      workshop
                        ? 'gf-input'
                        : 'border-black/[0.1] bg-[#f5f7f8] text-[#20262d] placeholder:text-[#9099a1] focus-visible:ring-2 focus-visible:ring-[#5271ff]/25',
                    ),
              )}
              placeholder={composerPlaceholder}
            />
            <div className={cn('flex items-center justify-between gap-2', hero ? 'px-2 pb-2' : 'mt-2')}>
              <span className={cn('font-mono text-[10px]', workshop ? 'gf-page-muted' : 'text-[#9099a1]')}>
                Enter 发送 · Shift+Enter 换行
              </span>
              <Button
                variant="primary"
                className={cn(
                  hero ? 'gf-forge-send-btn gf-btn-primary gf-interactive !border-0 !py-2.5' : '!rounded-lg !px-4 !py-2',
                  !hero &&
                    (workshop
                      ? 'gf-btn-primary gf-interactive !border-0'
                      : '!bg-[#20262d] !text-white hover:!bg-[#303940]'),
                )}
                disabled={disabled || !input.trim()}
                onClick={onSend}
              >
                <Send className="h-3.5 w-3.5" />
                {t('sendRequirement')}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  )
}
