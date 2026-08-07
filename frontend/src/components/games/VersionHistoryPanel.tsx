import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Eye, History, Loader2, Upload } from 'lucide-react'
import { gamesApi } from '@/api/games'
import { formatApiError } from '@/api/error-message'
import type { GameVersion } from '@/api/types'
import { formatRelativeTime } from '@/lib/relative-time'
import { useT } from '@/i18n/use-t'
import { useLocaleStore } from '@/stores/locale-store'
import { cn } from '@/lib/cn'
import { PublishNoteModal } from './PublishNoteModal'

type Props = {
  gameId: string
  currentVersion: number
  /** GET /games/{id} 已含 versions 时优先使用 */
  embeddedVersions?: GameVersion[]
  accessToken: string
  readOnly?: boolean
  /** 当前预览中的版本号 */
  previewVersion: number | null
  onPreview: (version: number) => void
  onPublished?: () => void
}

export function VersionHistoryPanel({
  gameId,
  currentVersion,
  embeddedVersions,
  accessToken,
  readOnly = false,
  previewVersion,
  onPreview,
  onPublished,
}: Props) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const hasEmbedded = Boolean(embeddedVersions && embeddedVersions.length > 0)

  const query = useQuery({
    queryKey: ['game-versions', gameId],
    enabled: Boolean(gameId && accessToken && !hasEmbedded),
    queryFn: () => gamesApi.listVersions(gameId, accessToken),
  })

  const versions = useMemo(() => {
    const rows = hasEmbedded ? embeddedVersions! : (query.data?.data ?? [])
    return [...rows].sort((a, b) => b.version - a.version)
  }, [hasEmbedded, embeddedVersions, query.data?.data])

  const [publishVersion, setPublishVersion] = useState<number | null>(null)
  const [publishing, setPublishing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handlePublish(note: string) {
    if (publishVersion == null) return
    setPublishing(true)
    setError(null)
    try {
      await gamesApi.submitPublish(gameId, publishVersion, note, accessToken)
      setPublishVersion(null)
      onPublished?.()
    } catch (e) {
      setError(formatApiError(e, t('submitPublishFailed')))
    } finally {
      setPublishing(false)
    }
  }

  if (!hasEmbedded && query.isLoading) {
    return (
      <div className="gf-page-muted flex items-center gap-2 px-1 py-2 text-xs">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        {t('loading')}
      </div>
    )
  }

  if (versions.length === 0) {
    return (
      <p className="gf-page-muted px-1 py-2 text-xs">{t('versionHistoryEmpty')}</p>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <History className="gf-page-muted h-3.5 w-3.5" />
        <p className="font-mono text-[10px] tracking-[0.14em] gf-page-muted uppercase">
          {t('versionHistory')}
        </p>
      </div>

      {error ? (
        <p role="alert" className="text-xs text-rose-400">
          {error}
        </p>
      ) : null}

      <ul className="max-h-44 space-y-1 overflow-y-auto pr-1">
        {versions.map((v) => {
          const isCurrent = v.version === currentVersion
          const isPreview = previewVersion === v.version
          return (
            <li
              key={v.version}
              className={cn(
                'flex flex-wrap items-center justify-between gap-2 rounded-lg border px-2.5 py-2 text-xs transition',
                isPreview
                  ? 'border-[rgba(var(--gf-primary-rgb),0.45)] bg-[rgba(var(--gf-primary-rgb),0.08)]'
                  : 'gf-border-subtle border bg-black/[0.02]',
              )}
            >
              <div className="min-w-0">
                <span className="gf-page-body font-medium">
                  v{v.version}
                  {isCurrent ? (
                    <span className="gf-text-accent ml-1.5 text-[10px] font-normal">
                      {t('versionCurrent')}
                    </span>
                  ) : null}
                </span>
                <p
                  className="gf-page-muted mt-0.5 font-mono text-[10px]"
                  title={new Date(v.created_at).toLocaleString()}
                >
                  {formatRelativeTime(v.created_at, locale)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  data-testid={`preview-v${v.version}`}
                  title={t('versionPreview')}
                  aria-label={t('versionPreview')}
                  onClick={() => onPreview(v.version)}
                  className={cn(
                    'gf-interactive inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 transition',
                    isPreview
                      ? 'gf-chip-active'
                      : 'gf-chip hover:bg-black/[0.04]',
                  )}
                >
                  <Eye className="h-3 w-3" />
                  {t('preview')}
                </button>
                {!readOnly && v.version >= 1 ? (
                  <button
                    type="button"
                    title={t('versionPublishThis')}
                    disabled={publishing}
                    onClick={() => setPublishVersion(v.version)}
                    className="gf-interactive inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 gf-chip transition hover:bg-black/[0.04] disabled:opacity-50"
                  >
                    <Upload className="h-3 w-3" />
                    {t('publish')}
                  </button>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>

      <PublishNoteModal
        open={publishVersion != null}
        gameTitle={`v${publishVersion ?? ''}`}
        defaultNote=""
        busy={publishing}
        onCancel={() => setPublishVersion(null)}
        onConfirm={(note) => void handlePublish(note)}
      />
    </div>
  )
}
