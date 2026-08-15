import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowUpRight, Play, Star } from 'lucide-react'
import type { PublicGame } from '@/api/public-games'
import { CreatorLink } from '@/components/creator/CreatorLink'
import { officialCoverUrl } from '@/lib/official-covers'
import { formatRelativeTime } from '@/lib/relative-time'
import { useT } from '@/i18n/use-t'
import { useLocaleStore } from '@/stores/locale-store'
import { cn } from '@/lib/cn'

const covers = [
  'bg-[radial-gradient(circle_at_20%_20%,rgba(232,121,249,0.55),transparent_45%),radial-gradient(circle_at_80%_70%,rgba(34,211,238,0.45),transparent_40%),linear-gradient(135deg,#2a1452,#120a26)]',
  'bg-[conic-gradient(from_210deg_at_40%_40%,rgba(34,211,238,0.4),transparent_40%,rgba(232,121,249,0.5)),linear-gradient(160deg,#1d1b4a,#120a26)]',
  'bg-[radial-gradient(ellipse_at_top,rgba(244,63,94,0.4),transparent_50%),radial-gradient(ellipse_at_bottom_right,rgba(217,70,239,0.36),transparent_45%),linear-gradient(145deg,#241438,#120a26)]',
]

function coverFor(id: string) {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i) * (i + 1)) % covers.length
  return covers[h]
}

type Props = {
  game: PublicGame
  compact?: boolean
  /** dark = 固定深色（Landing/Creator 用）；theme = 跟随 --gf-* 主题 token（discover 用） */
  variant?: 'dark' | 'theme'
  /** 是否显示精选星标（默认 true） */
  showFeaturedBadge?: boolean
}

export function PublicGameCard({
  game,
  compact = false,
  variant = 'dark',
  showFeaturedBadge = true,
}: Props) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const reduce = useReducedMotion()
  // 封面优先级链：真截图 cover_url → 官方静态 PNG officialCoverUrl → 渐变。
  // 任一级 onError 即降级到下一级。
  const [shotFailed, setShotFailed] = useState(false)
  const [officialFailed, setOfficialFailed] = useState(false)
  const official = officialCoverUrl(game.slug)
  const showShot = Boolean(game.cover_url) && !shotFailed
  const showOfficial = !showShot && Boolean(official) && !officialFailed
  const showFeatured = showFeaturedBadge && game.featured
  const theme = variant === 'theme'

  return (
    <motion.article
      layout
      whileHover={{ y: reduce ? 0 : -6, borderColor: 'rgba(217, 70, 239, 0.4)' }}
      transition={{ type: 'spring', stiffness: 320, damping: 24 }}
      className={cn(
        'group relative overflow-hidden rounded-2xl border backdrop-blur-xl',
        theme
          ? 'gf-glass gf-glass-hover'
          : 'border-white/10 bg-white/[0.04] shadow-[0_1px_2px_rgba(0,0,0,0.3)] hover:shadow-[0_0_28px_rgba(217,70,239,0.18)]',
        compact ? 'flex flex-row' : 'flex flex-col',
      )}
    >
      {/* 整卡可点：absolute 拉伸链接覆盖全卡。封面/标题等非交互内容默认在它下方，
          点击穿透到此处跳转试玩；CreatorLink 与「立即试玩」按钮用 relative z-[2] 抬到上方，
          保持各自独立可点。 */}
      <Link
        to={`/play/${game.slug}`}
        aria-label={`${t('playNow')} ${game.title}`}
        className={cn(
          'absolute inset-0 z-[1] rounded-2xl outline-none focus-visible:ring-2',
          theme ? 'focus-visible:ring-[var(--gf-primary)]' : 'focus-visible:ring-fuchsia-400/70',
        )}
      />

      <div
        className={cn(
          'relative z-0 shrink-0 overflow-hidden',
          compact ? 'h-full w-28 min-h-[88px]' : 'aspect-[16/10] w-full min-h-[160px]',
        )}
      >
        {showShot ? (
          <img
            src={game.cover_url!}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover"
            onError={() => setShotFailed(true)}
          />
        ) : showOfficial ? (
          <img
            src={official!}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover"
            onError={() => setOfficialFailed(true)}
          />
        ) : (
          <div className={cn('absolute inset-0', coverFor(game.game_id))}>
            <div className="absolute inset-0 opacity-40 mix-blend-screen [background-image:linear-gradient(115deg,transparent_40%,rgba(255,255,255,0.18)_50%,transparent_60%)]" />
          </div>
        )}

        {showFeatured ? (
          <span
            className={cn(
              'pointer-events-none absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider backdrop-blur-sm',
              theme
                ? 'gf-border-accent gf-bg-accent-soft gf-text-accent'
                : 'border-fuchsia-400/40 bg-[#161229]/70 text-fuchsia-300',
            )}
          >
            <Star className="h-3 w-3 fill-current" />
            {t('featuredBadge')}
          </span>
        ) : null}
      </div>

      <div className={cn('relative z-0 flex flex-1 flex-col justify-between', compact ? 'p-3' : 'space-y-3 p-4')}>
        <div>
          <h2
            className={cn(
              'leading-snug',
              theme ? 'text-[var(--gf-text)]' : 'text-white',
              compact ? 'text-base' : 'text-lg',
            )}
          >
            {game.title}
          </h2>
          <CreatorLink
            creator={game.creator}
            authorHandle={game.author_handle}
            authorDisplay={game.author_display}
            variant={variant}
            className="relative z-[2] mt-1 block"
          />
          <div
            className={cn(
              'mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-wider',
              theme ? 'text-[var(--gf-text-muted)]' : 'text-white/55',
            )}
          >
            <span>{t('playCount').replace('{n}', String(game.play_count))}</span>
            {game.published_at ? (
              <>
                <span className={theme ? 'opacity-30' : 'text-white/30'} aria-hidden>
                  ·
                </span>
                <span title={new Date(game.published_at).toLocaleString()}>
                  {formatRelativeTime(game.published_at, locale)}
                </span>
              </>
            ) : null}
          </div>
        </div>

        <Link
          to={`/play/${game.slug}`}
          aria-label={`${t('playNow')} ${game.title}`}
          className={cn(
            'relative z-[2] inline-flex w-fit cursor-pointer items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition',
            theme
              ? 'gf-btn-primary'
              : 'bg-white/90 text-black hover:bg-white hover:shadow-[0_0_18px_rgba(34,211,238,0.35)]',
          )}
        >
          <Play className="h-3.5 w-3.5" />
          {t('playNow')}
          <ArrowUpRight className="h-3.5 w-3.5 opacity-60" />
        </Link>
      </div>
    </motion.article>
  )
}
