import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowUpRight, Play } from 'lucide-react'
import type { PublicGame } from '@/api/public-games'
import { CreatorLink } from '@/components/creator/CreatorLink'
import { formatRelativeTime } from '@/lib/relative-time'
import { useT } from '@/i18n/use-t'
import { useLocaleStore } from '@/stores/locale-store'
import { cn } from '@/lib/cn'

const covers = [
  'bg-[radial-gradient(circle_at_20%_20%,rgba(168,85,247,0.55),transparent_45%),radial-gradient(circle_at_80%_70%,rgba(34,211,238,0.4),transparent_40%),linear-gradient(135deg,#1a1030,#0B0E14)]',
  'bg-[conic-gradient(from_210deg_at_40%_40%,rgba(34,211,238,0.35),transparent_40%,rgba(168,85,247,0.45)),linear-gradient(160deg,#101828,#0B0E14)]',
  'bg-[radial-gradient(ellipse_at_top,rgba(244,63,94,0.35),transparent_50%),radial-gradient(ellipse_at_bottom_right,rgba(34,211,238,0.3),transparent_45%),linear-gradient(145deg,#18122b,#0B0E14)]',
]

function coverFor(id: string) {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i) * (i + 1)) % covers.length
  return covers[h]
}

type Props = {
  game: PublicGame
  compact?: boolean
}

export function PublicGameCard({ game, compact = false }: Props) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)

  return (
    <motion.article
      layout
      whileHover={{ y: -6, borderColor: 'rgba(34, 211, 238, 0.45)' }}
      transition={{ type: 'spring', stiffness: 320, damping: 24 }}
      className={cn(
        'group overflow-hidden rounded-2xl border border-white/10 bg-white/[0.06] backdrop-blur-md transition-shadow hover:shadow-[0_0_24px_rgba(34,211,238,0.12)]',
        compact ? 'flex flex-row' : 'flex flex-col',
      )}
    >
      <div
        className={cn(
          'relative shrink-0 overflow-hidden',
          coverFor(game.game_id),
          compact ? 'h-full w-28 min-h-[88px]' : 'h-32 w-full',
        )}
      >
        <div className="absolute inset-0 opacity-40 mix-blend-screen [background-image:linear-gradient(115deg,transparent_40%,rgba(255,255,255,0.18)_50%,transparent_60%)]" />
        <div className="absolute bottom-2 left-2 font-mono text-[10px] tracking-wider text-white/55 uppercase">
          {t('playCount').replace('{n}', String(game.play_count))}
        </div>
      </div>

      <div className={cn('flex flex-1 flex-col justify-between', compact ? 'p-3' : 'space-y-3 p-4')}>
        <div>
          <h2 className={cn('leading-snug text-white', compact ? 'text-base' : 'text-lg')}>
            {game.title}
          </h2>
          <CreatorLink
            creator={game.creator}
            authorHandle={game.author_handle}
            authorDisplay={game.author_display}
            className="mt-1 block"
          />
          <p
            className="mt-1.5 font-mono text-[10px] text-white/45"
            title={new Date(game.published_at).toLocaleString()}
          >
            {formatRelativeTime(game.published_at, locale)}
          </p>
        </div>

        <Link
          to={`/play/${game.slug}`}
          className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-white/90 px-3 py-2 text-xs font-medium text-black transition hover:bg-white"
        >
          <Play className="h-3.5 w-3.5" />
          {t('playNow')}
          <ArrowUpRight className="h-3.5 w-3.5 opacity-60" />
        </Link>
      </div>
    </motion.article>
  )
}
