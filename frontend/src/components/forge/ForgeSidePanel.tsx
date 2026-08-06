import { GamePlayer } from '@/components/game/GamePlayer'
import { cn } from '@/lib/cn'
import type { TimelineItem } from './RunTimeline'

type Tab = 'log' | 'play'

type Props = {
  tab: Tab
  onTabChange: (t: Tab) => void
  items: TimelineItem[]
  previewUrl: string | null
  gameTitle: string
}

export function ForgeSidePanel({ tab, onTabChange, items, previewUrl, gameTitle }: Props) {
  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#12151a]">
      <header className="flex items-center gap-1 border-b border-white/[0.06] p-2">
        {(
          [
            ['log', '事件日志'],
            ['play', '试玩'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => onTabChange(id)}
            className={cn(
              'cursor-pointer rounded-lg px-3 py-1.5 font-mono text-[11px] tracking-wide uppercase transition-colors',
              tab === id
                ? 'bg-white/[0.1] text-white'
                : 'text-white/40 hover:bg-white/[0.05] hover:text-white/70',
            )}
          >
            {label}
          </button>
        ))}
      </header>

      {tab === 'log' ? (
        <div className="flex-1 space-y-2 overflow-y-auto p-3 font-mono text-[11px] leading-relaxed">
          {items.length === 0 ? (
            <p className="py-10 text-center text-white/30">等待 run 事件…</p>
          ) : (
            items.map((it) => (
              <div key={it.id} className="rounded-lg bg-black/25 px-2.5 py-2 text-white/65 ring-1 ring-white/[0.04]">
                <span className="text-teal-300/80">[{new Date(it.at).toLocaleTimeString()}]</span>{' '}
                {it.label}
                {it.detail ? <div className="mt-0.5 text-white/40">{it.detail}</div> : null}
              </div>
            ))
          )}
        </div>
      ) : previewUrl ? (
        <div className="min-h-0 flex-1 p-2">
          <GamePlayer src={previewUrl} title={gameTitle} variant="console" />
        </div>
      ) : (
        <div className="grid flex-1 place-items-center px-6 text-center">
          <div>
            <p className="text-sm text-white/55">尚无构建产物</p>
            <p className="mt-1 text-xs text-white/30">run 完成后自动切到试玩</p>
          </div>
        </div>
      )}
    </section>
  )
}
