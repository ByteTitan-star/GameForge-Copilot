import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowUpRight, Loader2, Pencil, Sparkles, Trash2, Upload } from 'lucide-react'
import { GameStatus } from '@/api/enums'
import type { GameSummary } from '@/api/types'
import { formatRelativeTime } from '@/lib/relative-time'
import { cn } from '@/lib/cn'
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

function blurbFor(g: GameSummary) {
  if (g.status === GameStatus.published) return '已上架公开试玩；可继续迭代出新版本。'
  if (g.status === GameStatus.rejected) return '审批驳回。修改后可再次提交发布。'
  if (g.status === GameStatus.submitted || g.status === GameStatus.reviewing)
    return '已进入审批队列，通过后将分配公开 slug。'
  return '草稿仅自己可见。完善玩法后可提交发布审核。'
}

export type GameCardProps = {
  game: GameSummary
  /** 试用只读：隐藏发布/删除，编辑改为查看 */
  readOnly?: boolean
  onPublish: (g: GameSummary, note: string) => Promise<void>
  onRequestDelete: (g: GameSummary) => void
  onRename?: (g: GameSummary, title: string) => Promise<void>
}

export function GameCard({
  game: g,
  readOnly = false,
  onPublish,
  onRequestDelete,
  onRename,
}: GameCardProps) {
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
        'group relative mb-4 break-inside-avoid overflow-hidden rounded-2xl border border-white/[0.06]',
        'bg-white/[0.03] backdrop-blur-md',
        flash && 'ring-2 ring-emerald-300/80',
      )}
    >
      {burst ? <span className="card-burst" aria-hidden /> : null}

      <div className={cn('relative h-28 overflow-hidden', coverFor(g.game_id))}>
        <div className="absolute inset-0 opacity-40 mix-blend-screen [background-image:linear-gradient(115deg,transparent_40%,rgba(255,255,255,0.18)_50%,transparent_60%)]" />
        <div className="absolute top-3 right-3">
          <StatusBadge status={g.status} />
        </div>
        <div className="absolute bottom-3 left-3 font-mono text-[10px] tracking-wider text-white/50 uppercase">
          v{g.current_version}
        </div>
      </div>

      <div className="space-y-3 p-4">
        <div>
          <h2 className="text-lg leading-snug text-white/95">{g.title}</h2>
          <p className="mt-1.5 text-xs leading-relaxed text-white/45">{blurbFor(g)}</p>
        </div>

        <p
          className="font-mono text-[11px] text-white/35"
          title={new Date(g.updated_at).toLocaleString()}
        >
          {formatRelativeTime(g.updated_at)}
          <span className="ml-1 opacity-0 transition group-hover:opacity-100">
            · {new Date(g.updated_at).toLocaleString()}
          </span>
        </p>

        <div className="flex flex-wrap gap-1.5">
          <Link
            to={`/forge/${g.game_id}`}
            className="rounded-lg px-2.5 py-1.5 text-xs text-white/70 ring-1 ring-white/10 transition hover:bg-white/[0.06]"
          >
            {readOnly ? '查看' : '编辑'}
          </Link>
          {playTo ? (
            <Link
              to={playTo}
              className="inline-flex items-center gap-1 rounded-lg bg-white/90 px-2.5 py-1.5 text-xs font-medium text-black transition hover:bg-white"
            >
              {g.status === GameStatus.published ? '试玩' : '预览'}
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          ) : null}
          {canPublish ? (
            <button
              type="button"
              disabled={publishing}
              onClick={() => setPublishOpen(true)}
              className="inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-cyan-200 ring-1 ring-cyan-400/30 transition hover:bg-cyan-400/10 disabled:opacity-60"
            >
              {publishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              发布
            </button>
          ) : null}
          {canRename ? (
            <button
              type="button"
              onClick={() => {
                setRenameTitle(g.title)
                setRenameOpen(true)
              }}
              className="inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-white/55 ring-1 ring-white/10 transition hover:bg-white/[0.06]"
            >
              <Pencil className="h-3.5 w-3.5" />
              重命名
            </button>
          ) : null}
          {canDelete ? (
            <button
              type="button"
              onClick={() => onRequestDelete(g)}
              className="inline-flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-rose-300 ring-1 ring-rose-400/25 transition hover:bg-rose-500/10"
            >
              <Trash2 className="h-3.5 w-3.5" />
              删除
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
          <div className="w-full max-w-sm space-y-3 rounded-2xl border border-white/10 bg-[#161a20] p-4">
            <h3 className="text-sm text-white/90">重命名游戏</h3>
            <input
              value={renameTitle}
              onChange={(e) => setRenameTitle(e.target.value)}
              className="h-10 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-sm text-white outline-none"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="cursor-pointer rounded-lg px-3 py-1.5 text-xs text-white/50"
                onClick={() => setRenameOpen(false)}
              >
                取消
              </button>
              <button
                type="button"
                disabled={renaming || !renameTitle.trim()}
                className="cursor-pointer rounded-lg bg-cyan-400 px-3 py-1.5 text-xs font-medium text-black disabled:opacity-50"
                onClick={() => void handleRename()}
              >
                {renaming ? <Loader2 className="inline h-3.5 w-3.5 animate-spin" /> : '保存'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </motion.article>
  )
}
