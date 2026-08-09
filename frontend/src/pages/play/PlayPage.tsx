import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Copy, Check, Image, Maximize2, Smartphone } from 'lucide-react'
import { playApi } from '@/api/play'
import { CreatorLink } from '@/components/creator/CreatorLink'
import { GamePlayer } from '@/components/game/GamePlayer'
import { ReactionButtons } from '@/components/social/ReactionButtons'
import { SharePosterModal } from '@/components/share/SharePosterModal'
import { useDocumentMeta } from '@/hooks/use-document-meta'
import { playArtifactUrl } from '@/lib/hosting'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { cn } from '@/lib/cn'

export function PlayPage() {
  const t = useT()
  const { slug } = useParams()
  const safeSlug = slug ?? ''
  const src = playArtifactUrl(safeSlug)
  const stageRef = useRef<HTMLElement>(null)
  const [copied, setCopied] = useState(false)
  const [landscapeHint, setLandscapeHint] = useState(false)
  const [posterOpen, setPosterOpen] = useState(false)
  const [showEscHint, setShowEscHint] = useState(false)
  const token = useAuthStore((s) => s.access_token)

  const metaQ = useQuery({
    queryKey: ['play-meta', safeSlug],
    enabled: Boolean(safeSlug),
    queryFn: () => playApi.getMeta(safeSlug),
  })

  const meta = metaQ.data
  const title = meta?.title ?? safeSlug
  const shareUrl = typeof window !== 'undefined' ? window.location.href : ''

  useDocumentMeta({
    title: `${title} · GameForge`,
    description: meta?.author_display
      ? `${title} — ${meta.author_display} · ${t('playCount').replace('{n}', String(meta?.play_count ?? 0))}`
      : title,
    url: shareUrl,
  })

  function enterFullscreen() {
    if (!stageRef.current?.requestFullscreen) return
    void stageRef.current.requestFullscreen()
  }

  async function copyShareLink() {
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      /* ignore */
    }
  }

  // 进入全屏后短暂提示「ESC 退出全屏试玩」
  useEffect(() => {
    function onFsChange() {
      if (document.fullscreenElement) {
        setShowEscHint(true)
        window.setTimeout(() => setShowEscHint(false), 3000)
      } else {
        setShowEscHint(false)
      }
    }
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  return (
    <div className="flex h-[100svh] flex-col bg-[#0a0a0a] text-white pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)]">
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-6 sm:px-6 md:py-8">
        <header className="mb-6 flex shrink-0 flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <Link
              to="/discover"
              className="inline-flex items-center gap-1.5 text-sm text-white/55 transition hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              {t('playPageBackDiscover')}
            </Link>
            <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-white/45">
              <CreatorLink
                authorHandle={meta?.author_handle}
                authorDisplay={meta?.author_display}
                className="!text-white/45 hover:!text-white/80"
              />
              {meta?.published_at ? (
                <span>
                  {t('playPublishedAt')}: {new Date(meta.published_at).toLocaleDateString()}
                </span>
              ) : null}
              {meta ? <span>{t('playCount').replace('{n}', String(meta.play_count))}</span> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void copyShareLink()}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 text-xs text-white/80 transition hover:border-white/30 hover:text-white"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? t('playShareCopied') : t('playShareLink')}
            </button>
            <button
              type="button"
              onClick={() => setPosterOpen(true)}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 text-xs text-white/80 transition hover:border-white/30 hover:text-white"
            >
              <Image className="h-3.5 w-3.5" />
              {t('sharePosterBtn')}
            </button>
            <button
              type="button"
              onClick={() => setLandscapeHint((v) => !v)}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-white/15 bg-white/[0.04] px-3 py-2 text-xs text-white/80 transition hover:border-white/30 md:hidden"
            >
              <Smartphone className="h-3.5 w-3.5" />
              {t('playLandscapeHint')}
            </button>
          </div>
        </header>

        {meta?.game_id ? (
          <ReactionButtons gameId={meta.game_id} accessToken={token} className="mb-4 shrink-0" />
        ) : null}

        {landscapeHint ? (
          <p className="mb-4 shrink-0 rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-100 md:hidden">
            {t('playLandscapeHint')}
          </p>
        ) : null}

        <section
          ref={stageRef}
          className={cn('relative min-h-0 flex-1 overflow-hidden rounded-2xl border border-white/10 bg-black')}
        >
          {showEscHint ? (
            <div className="absolute left-3 top-3 z-20 rounded-lg bg-black/60 px-3 py-1.5 text-xs text-white/85 backdrop-blur-md">
              {t('playEscExit')}
            </div>
          ) : null}
          <div className="absolute right-3 top-3 z-10 flex gap-2">
            <button
              type="button"
              title={t('fullscreenPlay')}
              aria-label={t('fullscreenPlay')}
              onClick={enterFullscreen}
              className="grid h-9 w-9 cursor-pointer place-items-center rounded-lg bg-black/50 text-white/70 backdrop-blur-md transition hover:text-white"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          </div>
          <GamePlayer src={src} title={title} variant="stage" className="h-full" />
        </section>
      </div>

      <SharePosterModal
        open={posterOpen}
        title={title}
        slug={safeSlug}
        onClose={() => setPosterOpen(false)}
      />
    </div>
  )
}
