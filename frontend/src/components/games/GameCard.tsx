import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowUpRight, EyeOff, History, Loader2, Pencil, Sparkles, Trash2, Undo2, Upload } from 'lucide-react'
import { GameStatus } from '@/api/enums'
import type { GameSummary } from '@/api/types'
import type { MessageKey } from '@/i18n/messages'
import { formatRelativeTime } from '@/lib/relative-time'
import { cn } from '@/lib/cn'
import { useT } from '@/i18n/use-t'
import { useLocaleStore } from '@/stores/locale-store'
import { PublishNoteModal } from './PublishNoteModal'
import { StatusBadge } from './StatusBadge'

const covers = [
  'bg-[radial-gradient(circle_at_20%_20%,rgba(168,85,247,0.55),transparent_45%),radial-gradient(circle_at_80%_70%,rgba(34,211,238,0.4),transparent_40%),linear-gradient(135deg,#1a1030,#0B0E14)]',
  'bg-[conic-gradient(from_210deg_at_40%_40%,rgba(34,211,238,0.35),transparent_40%,rgba(168,85,247,0.45)),linear-gradient(160deg,#101828,#0B0E14)]',
  'bg-[radial-gradient(ellipse_at_top,rgba(244,63,94,0.35),transparent_50%),radial-gradient(ellipse_at_bottom_right,rgba(34,211,238,0.3),transparent_45%),linear-gradient(145deg,#18122b,#0B0E14)]',
  'bg-[linear-gradient(120deg,rgba(168,85,247,0.35),transparent_40%),linear-gradient(300deg,rgba(34,211,238,0.3),transparent_45%),linear-gradient(#131821,#0B0E14)]',
]

function coverFor(id: string) {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i) * (i + 1)) % covers.length
  return covers[h]
}

function blurbFor(g: GameSummary, t: (key: MessageKey) => string) {
  if (g.status === GameStatus.published) return t('blurbPublished')
  if (g.status === GameStatus.rejected) return t('blurbRejected')
  if (g.status === GameStatus.submitted || g.status === GameStatus.reviewing) return t('blurbPipeline')
  return t('blurbDraft')
}

export type GameCardProps = {
  game: GameSummary
  /** 试用只读：隐藏发布/删除/下架/撤回，编辑改为查看 */
  readOnly?: boolean
  selectable?: boolean
  selected?: boolean
  onToggleSelect?: (id: string) => void
  onPublish: (g: GameSummary, note: string) => Promise<void>
  onRequestDelete: (g: GameSummary) => void
  onRequestUnpublish?: (g: GameSummary) => void
  onRequestWithdraw?: (g: GameSummary) => void
  onRename?: (g: GameSummary, title: string) => Promise<void>
  onOpenDetail?: (g: GameSummary) => void
}

export function GameCard({
  game: g,
  readOnly = false,
  selectable = false,
  selected = false,
  onToggleSelect,
  onPublish,
  onRequestDelete,
  onRequestUnpublish,
  onRequestWithdraw,
  onRename,
  onOpenDetail,
}: GameCardProps) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const [publishing, setPublishing] = useState(false)
  const [publishOpen, setPublishOpen] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [renameTitle, setRenameTitle] = useState(g.title)
  const [flash, setFlash] = useState(false)
  const [burst, setBurst] = useState(false)

  const playTo =
    g.status === GameStatus.published && g.slug
      ? `/play/${g.slug}`
      : g.current_version > 0
        ? `/draft/${g.game_id}/${g.current_version}`
        : null

  const canPublish =
    !readOnly &&
    g.current_version > 0 &&
    (g.status === GameStatus.draft ||
      g.status === GameStatus.rejected ||
      g.status === GameStatus.taken_down)

  const canDelete =
    !readOnly &&
    (g.status === GameStatus.draft ||
      g.status === GameStatus.rejected ||
      g.status === GameStatus.taken_down)

  const canUnpublish = !readOnly && g.status === GameStatus.published && Boolean(onRequestUnpublish)

  const canWithdraw =
    !readOnly &&
    (g.status === GameStatus.submitted || g.status === GameStatus.reviewing) &&
    Boolean(onRequestWithdraw)

  const canRename =
    !readOnly &&
    onRename &&
    (g.status === GameStatus.draft ||
      g.status === GameStatus.rejected ||
      g.status === GameStatus.taken_down)

  async function handleRename() {
    if (!onRename || renaming) return
    const title = renameTitle.trim()
    if (!title || title === g.title) {
      setRenameOpen(false)
      return
    }
    setRenaming(true)
    try {
      await onRename(g, title)
      setRenameOpen(false)
    } finally {
      setRenaming(false)
    }
  }

  async function handlePublish(note: string) {
    if (publishing) return
    setPublishing(true)
    try {
      await onPublish(g, note)
      setPublishOpen(false)
      setBurst(true)
      setFlash(true)
      window.setTimeout(() => setFlash(false), 700)
      window.setTimeout(() => setBurst(false), 900)
    } finally {
      setPublishing(false)
    }
  }

  return (
    <motion.article
      layout
      style={{ transformStyle: 'preserve-3d', perspective: 900 }}
      exit={{ scale: 0.85, opacity: 0, height: 0, marginBottom: 0, transition: { duration: 0.35 } }}
      whileHover={{
        y: -8,
        rotateX: 2,
        rotateY: 4,
        boxShadow: '0 0 20px rgba(34, 211, 238, 0.15)',
        borderColor: 'rgba(34, 211, 238, 0.45)',
      }}
      transition={{ type: 'spring', stiffness: 320, damping: 24 }}
      className={cn(
        'group relative overflow-hidden rounded-2xl gf-glass gf-glass-hover transition-all duration-300',
        flash && 'ring-2 ring-emerald-300/80',
      )}
    >
      {burst ? <span className="card-burst" aria-hidden /> : null}

      <div className={cn('relative h-28 overflow-hidden', coverFor(g.game_id))}>
        <div className="absolute inset-0 opacity-40 mix-blend-screen [background-image:linear-gradient(115deg,transparent_40%,rgba(255,255,255,0.18)_50%,transparent_60%)]" />
        {selectable ? (
          <label
            className="absolute top-2.5 left-2.5 z-10 inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-black/30 px-2 py-1 text-white backdrop-blur-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect?.(g.game_id)}
              className="gf-checkbox"
            />
          </label>
        ) : null}
        <div className="absolute top-3 right-3">
          <StatusBadge status={g.status} />
        </div>
        <div className="absolute bottom-3 left-3 font-mono text-[10px] tracking-wider text-white/50 uppercase">
          v{g.current_version}
        </div>
      </div>

      <div className="space-y-3 p-4">
        <div>
          <h2 className="text-lg leading-snug text-[var(--gf-text)]">{g.title}</h2>
          <p className="gf-page-muted mt-1.5 text-xs leading-relaxed">{blurbFor(g, t)}</p>
        </div>

        <p
          className="gf-page-muted font-mono text-[11px]"
          title={new Date(g.updated_at).toLocaleString()}
        >
          {formatRelativeTime(g.updated_at, locale)}
          <span className="ml-1 opacity-0 transition group-hover:opacity-100">
            · {new Date(g.updated_at).toLocaleString()}
          </span>
        </p>

        <div className="flex flex-wrap gap-1.5">
          {onOpenDetail && g.current_version > 0 ? (
            <button
              type="button"
              onClick={() => onOpenDetail(g)}
              className="gf-chip gf-interactive inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs transition hover:bg-black/[0.03]"
            >
              <History className="h-3.5 w-3.5" />
              {t('gameViewDetail')}
            </button>
          ) : null}
          <Link
            to={`/forge/${g.game_id}`}
            className="gf-chip gf-interactive rounded-lg px-2.5 py-1.5 text-xs transition hover:bg-black/[0.03]"
          >
            {readOnly ? t('view') : t('edit')}
          </Link>
          {playTo ? (
            <Link
              to={playTo}
              className="inline-flex items-center gap-1 rounded-lg bg-white/90 px-2.5 py-1.5 text-xs font-medium text-black transition hover:bg-white"
            >
              {g.status === GameStatus.published ? t('playable') : t('preview')}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          ) : null}
          {canPublish ? (
            <button
              type="button"
              disabled={publishing}
              onClick={() => setPublishOpen(true)}
              className="gf-chip-active gf-interactive inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs transition disabled:opacity-60"
            >
              {publishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              {t('publish')}
            </button>
          ) : null}
          {canRename ? (
            <button
              type="button"
              onClick={() => {
                setRenameTitle(g.title)
                setRenameOpen(true)
              }}
              className="gf-page-muted gf-chip inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs transition hover:bg-black/[0.03]"
            >
              <Pencil className="h-3.5 w-3.5" />
              {t('rename')}
            </button>
          ) : null}
          {canWithdraw ? (
            <button
              type="button"
              onClick={() => onRequestWithdraw?.(g)}
              className="gf-page-muted gf-chip gf-interactive inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs transition hover:bg-black/[0.03]"
            >
              <Undo2 className="h-3.5 w-3.5" />
              {t('withdrawReview')}
            </button>
          ) : null}
          {canUnpublish ? (
            <button
              type="button"
              onClick={() => onRequestUnpublish?.(g)}
              className="gf-page-muted gf-chip gf-interactive inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs transition hover:bg-black/[0.03]"
            >
              <EyeOff className="h-3.5 w-3.5" />
              {t('unpublish')}
            </button>
          ) : null}
          {canDelete ? (
            <button
              type="button"
              onClick={() => onRequestDelete(g)}
              className="inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-rose-300 ring-1 ring-rose-400/25 transition hover:bg-rose-500/10"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {t('delete')}
            </button>
          ) : null}
        </div>
      </div>

      {g.status === GameStatus.published ? (
        <Sparkles className="pointer-events-none absolute right-3 bottom-3 h-3.5 w-3.5 text-cyan-300/30" />
      ) : null}

      <PublishNoteModal
        open={publishOpen}
        gameTitle={g.title}
        defaultNote=""
        busy={publishing}
        onCancel={() => setPublishOpen(false)}
        onConfirm={(note) => void handlePublish(note)}
      />

      {renameOpen ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="dialog">
          <div className="gf-glass w-full max-w-sm space-y-3 rounded-2xl p-4">
            <h3 className="gf-page-body text-sm">{t('renameGameTitle')}</h3>
            <input
              value={renameTitle}
              onChange={(e) => setRenameTitle(e.target.value)}
              className="gf-input h-10 w-full rounded-xl px-3 text-sm"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="gf-page-muted cursor-pointer rounded-lg px-3 py-1.5 text-xs"
                onClick={() => setRenameOpen(false)}
              >
                {t('cancel')}
              </button>
              <button
                type="button"
                disabled={renaming || !renameTitle.trim()}
                className="gf-btn-primary gf-interactive cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                onClick={() => void handleRename()}
              >
                {renaming ? <Loader2 className="inline h-3.5 w-3.5 animate-spin" /> : t('save')}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </motion.article>
  )
}
