import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowUpRight,
  Clock,
  EyeOff,
  History,
  Loader2,
  MoreHorizontal,
  Pencil,
  Play,
  Trash2,
  Undo2,
  Upload,
} from 'lucide-react'
import { GameStatus } from '@/api/enums'
import type { GameSummary } from '@/api/types'
import type { MessageKey } from '@/i18n/messages'
import { formatRelativeTime } from '@/lib/relative-time'
import { resolveHostingUrl } from '@/lib/hosting'
import { cn } from '@/lib/cn'
import { useT } from '@/i18n/use-t'
import { useLocaleStore } from '@/stores/locale-store'
import { PublishNoteModal } from './PublishNoteModal'
import { StatusBadge } from './StatusBadge'

const covers = [
  'bg-[radial-gradient(circle_at_18%_22%,rgba(139,92,246,0.55),transparent_48%),radial-gradient(circle_at_82%_78%,rgba(37,99,235,0.45),transparent_42%),linear-gradient(145deg,#1e1b4b,#0f172a)]',
  'bg-[radial-gradient(circle_at_75%_20%,rgba(6,182,212,0.45),transparent_45%),radial-gradient(circle_at_20%_80%,rgba(37,99,235,0.4),transparent_40%),linear-gradient(160deg,#0c4a6e,#0f172a)]',
  'bg-[radial-gradient(ellipse_at_top,rgba(15,23,42,0.2),transparent_50%),radial-gradient(ellipse_at_bottom_right,rgba(8,145,178,0.4),transparent_45%),linear-gradient(145deg,#111827,#0f766e)]',
  'bg-[linear-gradient(125deg,rgba(59,130,246,0.45),transparent_42%),linear-gradient(300deg,rgba(139,92,246,0.4),transparent_48%),linear-gradient(#1e293b,#312e81)]',
  'bg-[radial-gradient(circle_at_30%_30%,rgba(14,165,233,0.4),transparent_45%),linear-gradient(150deg,#0f172a,#164e63)]',
  'bg-[radial-gradient(circle_at_70%_25%,rgba(168,85,247,0.5),transparent_40%),linear-gradient(160deg,#1e1b4b,#0c4a6e)]',
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

const secondaryBtn =
  'gf-interactive inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-[10px] border border-[var(--gf-border)] bg-[var(--gf-surface)] px-3 text-xs font-medium text-[var(--gf-text)] transition hover:border-[rgba(var(--gf-primary-rgb),0.35)] hover:bg-black/[0.03]'

const primaryBtn =
  'gf-btn-primary gf-interactive inline-flex h-9 cursor-pointer items-center justify-center gap-1.5 rounded-[10px] px-3.5 text-xs font-semibold'

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
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const [coverFailed, setCoverFailed] = useState(false)

  const playTo =
    g.status === GameStatus.published && g.slug
      ? `/play/${g.slug}`
      : g.current_version > 0
        ? `/draft/${g.game_id}/${g.current_version}`
        : null

  const isDraftPlay = playTo?.startsWith('/draft/')
  const isPublished = g.status === GameStatus.published

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

  const canUnpublish = !readOnly && isPublished && Boolean(onRequestUnpublish)

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

  const hasMenuItems = canWithdraw || canUnpublish || canDelete

  useEffect(() => {
    if (!menuOpen) return
    function onPointerDown(e: MouseEvent) {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false)
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

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
      setFlash(true)
      window.setTimeout(() => setFlash(false), 700)
    } finally {
      setPublishing(false)
    }
  }

  function openPlay() {
    if (!playTo) return
    if (isDraftPlay) window.open(playTo, '_blank', 'noopener,noreferrer')
  }

  return (
    <motion.article
      layout
      whileHover={{ y: -3 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={cn(
        'group gf-games-card relative flex min-h-[320px] flex-col overflow-hidden rounded-2xl border border-[var(--gf-border)] bg-[var(--gf-surface)] shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-[border-color,box-shadow] duration-200',
        'hover:border-[rgba(var(--gf-primary-rgb),0.35)] hover:shadow-[0_12px_28px_rgba(15,23,42,0.08)]',
        flash && 'ring-2 ring-emerald-300/80',
      )}
    >
      <div className={cn('relative h-[140px] shrink-0 overflow-hidden', coverFor(g.game_id))}>
        {g.cover_url && !coverFailed ? (
          <img
            src={resolveHostingUrl(g.cover_url)}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
            onError={() => setCoverFailed(true)}
          />
        ) : (
          <div
            className="pointer-events-none absolute inset-0 opacity-50 mix-blend-screen transition duration-300 group-hover:opacity-70"
            style={{
              backgroundImage:
                'linear-gradient(115deg,transparent 38%,rgba(255,255,255,0.16) 50%,transparent 62%)',
            }}
            aria-hidden
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/35 via-transparent to-black/10" />
        {selectable ? (
          <label
            className="absolute top-2.5 left-2.5 z-10 inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-black/35 px-2 py-1 text-white backdrop-blur-sm"
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
        <div className="absolute bottom-3 left-3 rounded-md bg-black/35 px-2 py-0.5 font-mono text-[11px] tracking-wider text-white/85 backdrop-blur-sm">
          V{g.current_version}
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4 sm:p-5">
        <div className="min-w-0 flex-1">
          <h2 className="line-clamp-2 text-[17px] font-semibold leading-[1.45] text-[var(--gf-text)]">
            {g.title}
          </h2>
          <p className="gf-page-muted mt-2 line-clamp-2 text-[13px] leading-relaxed">{blurbFor(g, t)}</p>
          <p
            className="mt-3 inline-flex items-center gap-1.5 text-[12px] text-[var(--gf-text-muted)] opacity-80"
            title={new Date(g.updated_at).toLocaleString()}
          >
            <Clock className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
            {formatRelativeTime(g.updated_at, locale)}
          </p>
        </div>

        <div className="flex items-center gap-2 border-t border-[var(--gf-border)] pt-3">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            {isPublished && playTo ? (
              <Link to={playTo} className={primaryBtn}>
                <Play className="h-3.5 w-3.5 fill-current" />
                {t('playGame')}
              </Link>
            ) : (
              <Link to={`/forge/${g.game_id}`} className={primaryBtn}>
                {readOnly ? t('view') : t('continueEdit')}
              </Link>
            )}

            {isPublished ? (
              <Link to={`/forge/${g.game_id}`} className={secondaryBtn}>
                {readOnly ? t('view') : t('edit')}
              </Link>
            ) : null}

            {onOpenDetail && g.current_version > 0 ? (
              <button type="button" onClick={() => onOpenDetail(g)} className={secondaryBtn}>
                <History className="h-3.5 w-3.5 opacity-70" />
                {t('gameViewDetail')}
              </button>
            ) : null}

            {!isPublished && playTo ? (
              isDraftPlay ? (
                <button type="button" onClick={openPlay} className={secondaryBtn}>
                  {t('preview')}
                  <ArrowUpRight className="h-3.5 w-3.5 opacity-70" />
                </button>
              ) : (
                <Link to={playTo} className={secondaryBtn}>
                  {t('preview')}
                  <ArrowUpRight className="h-3.5 w-3.5 opacity-70" />
                </Link>
              )
            ) : null}

            {canPublish ? (
              <button
                type="button"
                disabled={publishing}
                onClick={() => setPublishOpen(true)}
                className={cn(secondaryBtn, 'text-[var(--gf-primary)] disabled:opacity-60')}
              >
                {publishing ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Upload className="h-3.5 w-3.5" />
                )}
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
                className={secondaryBtn}
              >
                <Pencil className="h-3.5 w-3.5 opacity-70" />
                {t('rename')}
              </button>
            ) : null}
          </div>

          {hasMenuItems ? (
            <div ref={menuRef} className="relative shrink-0">
              <button
                type="button"
                aria-label={t('moreActions')}
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((v) => !v)}
                className="gf-interactive grid h-9 w-9 cursor-pointer place-items-center rounded-[10px] text-[var(--gf-text-muted)] transition hover:bg-black/[0.04] hover:text-[var(--gf-text)]"
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
              {menuOpen ? (
                <div
                  role="menu"
                  className="gf-border-subtle absolute right-0 bottom-full z-20 mb-1.5 w-44 overflow-hidden rounded-xl border bg-[var(--gf-surface)] py-1 shadow-[0_12px_32px_rgba(15,23,42,0.14)]"
                >
                  {canWithdraw ? (
                    <button
                      type="button"
                      role="menuitem"
                      className="gf-page-body flex w-full cursor-pointer items-center gap-2 px-3 py-2.5 text-left text-sm transition hover:bg-black/[0.03]"
                      onClick={() => {
                        setMenuOpen(false)
                        onRequestWithdraw?.(g)
                      }}
                    >
                      <Undo2 className="h-3.5 w-3.5 opacity-60" />
                      {t('withdrawReview')}
                    </button>
                  ) : null}
                  {canUnpublish ? (
                    <button
                      type="button"
                      role="menuitem"
                      className="gf-page-body flex w-full cursor-pointer items-center gap-2 px-3 py-2.5 text-left text-sm transition hover:bg-black/[0.03]"
                      onClick={() => {
                        setMenuOpen(false)
                        onRequestUnpublish?.(g)
                      }}
                    >
                      <EyeOff className="h-3.5 w-3.5 opacity-60" />
                      {t('unpublish')}
                    </button>
                  ) : null}
                  {canDelete ? (
                    <>
                      {(canWithdraw || canUnpublish) && (
                        <div className="gf-border-subtle my-1 border-t" />
                      )}
                      <button
                        type="button"
                        role="menuitem"
                        className="flex w-full cursor-pointer items-center gap-2 px-3 py-2.5 text-left text-sm text-rose-600 transition hover:bg-rose-50"
                        onClick={() => {
                          setMenuOpen(false)
                          onRequestDelete(g)
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {t('deleteGame')}
                      </button>
                    </>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

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
