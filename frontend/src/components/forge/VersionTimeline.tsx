import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Eye, History, Loader2, Upload } from 'lucide-react'
import { gamesApi } from '@/api/games'
import { formatApiError } from '@/api/error-message'
import type { GameVersion } from '@/api/types'
import { downloadFile } from '@/lib/download-file'
import { formatRelativeTime } from '@/lib/relative-time'
import { useT } from '@/i18n/use-t'
import { useLocaleStore } from '@/stores/locale-store'
import { cn } from '@/lib/cn'
import { PublishNoteModal } from '@/components/games/PublishNoteModal'

type Props = {
  gameId: string
  currentVersion: number
  latestVersion: number
  embeddedVersions?: GameVersion[]
  accessToken: string
  readOnly?: boolean
  previewVersion: number | null
  onPreview: (version: number) => void
  onActivated?: () => void
}

export function VersionTimeline({
  gameId,
  currentVersion,
  latestVersion,
  embeddedVersions,
  accessToken,
  readOnly = false,
  previewVersion,
  onPreview,
  onActivated,
}: Props) {
  const t = useT()
  const locale = useLocaleStore((s) => s.locale)
  const qc = useQueryClient()
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
  const [activating, setActivating] = useState(false)
  const [downloadingVersion, setDownloadingVersion] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const activePreview = previewVersion ?? currentVersion
  const canActivate =
    !readOnly && activePreview > 0 && activePreview !== currentVersion && !activating

  async function handleActivate() {
    if (!canActivate) return
    setActivating(true)
    setError(null)
    try {
      await gamesApi.activateVersion(gameId, activePreview, accessToken)
      await qc.invalidateQueries({ queryKey: ['game', gameId] })
      await qc.invalidateQueries({ queryKey: ['game-versions', gameId] })
      onActivated?.()
    } catch (e) {
      setError(formatApiError(e, t('versionActivateFailed')))
    } finally {
      setActivating(false)
    }
  }

  async function handlePublish(note: string) {
    if (publishVersion == null) return
    setPublishing(true)
    setError(null)
    try {
      await gamesApi.submitPublish(gameId, publishVersion, note, accessToken)
      setPublishVersion(null)
      onActivated?.()
    } catch (e) {
      setError(formatApiError(e, t('submitPublishFailed')))
    } finally {
      setPublishing(false)
    }
  }

  async function handleDownload(version: number) {
    setDownloadingVersion(version)
    setError(null)
    try {
      const file = await gamesApi.downloadVersion(gameId, version, accessToken)
      downloadFile(file.blob, file.filename ?? `game-v${version}.html`)
    } catch (e) {
      setError(formatApiError(e, t('versionDownloadFailed')))
    } finally {
      setDownloadingVersion(null)
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
    return <p className="gf-page-muted px-1 py-2 text-xs">{t('versionHistoryEmpty')}</p>
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 px-1">
        <div className="flex items-center gap-2">
          <History className="gf-page-muted h-3.5 w-3.5" />
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] gf-page-muted">
            {t('versionTimelineTitle')}
          </p>
        </div>
        {canActivate ? (
          <button
            type="button"
            disabled={activating}
            onClick={() => void handleActivate()}
            className="gf-text-accent cursor-pointer rounded-lg px-2 py-1 text-[10px] font-medium uppercase tracking-wide hover:bg-black/[0.04] disabled:opacity-50"
          >
            {activating ? t('loading') : t('versionSetCurrent')}
          </button>
        ) : null}
      </div>

      {error ? (
        <p role="alert" className="text-xs text-rose-500">
          {error}
        </p>
      ) : null}

      <ul className="max-h-52 space-y-1 overflow-y-auto pr-1">
        {versions.map((v) => {
          const isActive = v.version === currentVersion
          const isLatest = v.version === latestVersion
          const isPreview = activePreview === v.version
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
                  {isActive ? (
                    <span className="gf-text-accent ml-1.5 text-[10px] font-normal">{t('versionActive')}</span>
                  ) : null}
                  {isLatest ? (
                    <span className="ml-1.5 text-[10px] font-normal text-emerald-600">{t('versionLatest')}</span>
                  ) : null}
                </span>
                <p className="gf-page-muted mt-0.5 text-[11px]" title={new Date(v.created_at).toLocaleString()}>
                  {formatRelativeTime(v.created_at, locale)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  data-testid={`download-v${v.version}`}
                  title={downloadingVersion === v.version ? t('versionDownloading') : t('versionDownload')}
                  aria-label={downloadingVersion === v.version ? t('versionDownloading') : t('versionDownload')}
                  disabled={downloadingVersion !== null}
                  onClick={() => void handleDownload(v.version)}
                  className="gf-interactive inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md gf-chip transition hover:bg-black/[0.04] disabled:cursor-wait disabled:opacity-50"
                >
                  {downloadingVersion === v.version ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Download className="h-3.5 w-3.5" />
                  )}
                </button>
                <button
                  type="button"
                  data-testid={`preview-v${v.version}`}
                  title={t('versionPreview')}
                  onClick={() => onPreview(v.version)}
                  className={cn(
                    'gf-interactive inline-flex cursor-pointer items-center gap-1 rounded-md px-2 py-1 transition',
                    isPreview ? 'gf-chip-active' : 'gf-chip hover:bg-black/[0.04]',
                  )}
                >
                  <Eye className="h-3 w-3" />
                  {t('preview')}
                </button>
                {!readOnly && v.version >= 1 ? (
                  <button
                    type="button"
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

      <p className="gf-page-muted px-1 text-[11px] leading-relaxed">{t('versionTimelineHint')}</p>

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
