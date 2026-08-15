import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { ExternalLink, Loader2, X } from 'lucide-react'
import { gamesApi } from '@/api/games'
import type { GameSummary } from '@/api/types'
import { GamePlayer } from '@/components/game/GamePlayer'
import { VersionHistoryPanel } from '@/components/games/VersionHistoryPanel'
import { StatusBadge } from '@/components/games/StatusBadge'
import { mintDraftPreviewUrl } from '@/lib/hosting'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Props = {
  game: GameSummary | null
  accessToken: string
  readOnly?: boolean
  onClose: () => void
  onPublished?: () => void
}

export function GameDetailDrawer({
  game,
  accessToken,
  readOnly = false,
  onClose,
  onPublished,
}: Props) {
  const t = useT()
  const [previewVersion, setPreviewVersion] = useState<number | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  const detail = useQuery({
    queryKey: ['game-detail-drawer', game?.game_id],
    enabled: Boolean(game?.game_id && accessToken),
    queryFn: () => gamesApi.get(game!.game_id, accessToken),
  })

  useEffect(() => {
    if (!game || game.current_version < 1) {
      setPreviewVersion(null)
      setPreviewUrl(null)
      return
    }
    let cancelled = false
    setPreviewVersion(game.current_version)
    void mintDraftPreviewUrl(game.game_id, game.current_version, accessToken)
      .then((url) => {
        if (!cancelled) setPreviewUrl(url)
      })
      .catch(() => {
        if (!cancelled) setPreviewUrl(null)
      })
    return () => {
      cancelled = true
    }
  }, [game?.game_id, game?.current_version, accessToken])

  function onPreview(version: number) {
    if (!game) return
    setPreviewVersion(version)
    void mintDraftPreviewUrl(game.game_id, version, accessToken).then(setPreviewUrl)
  }

  return (
    <AnimatePresence>
      {game ? (
        <>
          <motion.button
            type="button"
            aria-label={t('close')}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 cursor-pointer bg-black/45 backdrop-blur-[2px]"
            onClick={onClose}
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-labelledby="game-detail-drawer-title"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l gf-border-subtle border bg-[var(--gf-surface,#fafafa)] shadow-2xl"
          >
            <header className="flex shrink-0 items-start justify-between gap-3 border-b gf-border-subtle border px-4 py-4">
              <div className="min-w-0">
                <p className="font-mono text-[10px] tracking-[0.14em] gf-page-muted uppercase">
                  {t('gameDetail')}
                </p>
                <h2 id="game-detail-drawer-title" className="mt-1 truncate text-lg font-medium gf-page-body">
                  {detail.data?.title ?? game.title}
                </h2>
                <div className="mt-2">
                  <StatusBadge status={game.status} />
                </div>
              </div>
              <button
                type="button"
                aria-label={t('close')}
                onClick={onClose}
                className="gf-interactive grid h-9 w-9 shrink-0 cursor-pointer place-items-center rounded-lg transition hover:bg-black/[0.04]"
              >
                <X className="h-4 w-4 gf-page-muted" />
              </button>
            </header>

            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
              {detail.isLoading ? (
                <p className="flex items-center gap-2 gf-page-muted text-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t('loading')}
                </p>
              ) : null}

              {previewUrl ? (
                <section className="space-y-2">
                  <p className="font-mono text-[10px] tracking-[0.14em] gf-page-muted uppercase">
                    {t('playView')}
                    {previewVersion ? ` · v${previewVersion}` : ''}
                  </p>
                  <GamePlayer
                    src={previewUrl}
                    title={game.title}
                    variant="console"
                    accessToken={accessToken}
                    className="min-h-[220px]"
                  />
                </section>
              ) : null}

              {game.current_version >= 1 ? (
                <VersionHistoryPanel
                  gameId={game.game_id}
                  currentVersion={detail.data?.current_version ?? game.current_version}
                  embeddedVersions={detail.data?.versions}
                  accessToken={accessToken}
                  readOnly={readOnly}
                  previewVersion={previewVersion}
                  onPreview={onPreview}
                  onPublished={() => {
                    void detail.refetch()
                    onPublished?.()
                  }}
                />
              ) : (
                <p className="gf-page-muted text-sm">{t('versionHistoryEmpty')}</p>
              )}
            </div>

            <footer className="shrink-0 border-t gf-border-subtle border px-4 py-3">
              <div className="flex flex-wrap gap-2">
                <Link
                  to={`/forge/${game.game_id}`}
                  className={cn('gf-btn-primary inline-flex items-center gap-1.5 px-4 py-2 text-xs')}
                >
                  {readOnly ? t('view') : t('edit')}
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
                <button
                  type="button"
                  onClick={onClose}
                  className="gf-chip gf-interactive cursor-pointer rounded-lg px-4 py-2 text-xs"
                >
                  {t('close')}
                </button>
              </div>
            </footer>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  )
}
