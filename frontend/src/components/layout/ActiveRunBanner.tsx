import { Link } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { RunStatus } from '@/api/enums'
import { useActiveRuns } from '@/hooks/use-active-runs'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { isTrialUser } from '@/lib/trial'

export function ActiveRunBanner() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const { data } = useActiveRuns(token)
  const trial = isTrialUser(user)

  if (!token || trial) return null
  const active = (data?.data ?? []).find(
    (r) => r.status === RunStatus.running || r.status === RunStatus.paused,
  )
  if (!active) return null

  const label =
    active.status === RunStatus.paused ? t('activeRunPausedBanner') : t('activeRunBanner')

  return (
    <div className="gf-active-run-banner mx-4 mb-3 flex items-center justify-between gap-3 rounded-xl border px-4 py-2.5 text-sm">
      <div className="flex min-w-0 items-center gap-2">
        <Loader2 className="h-4 w-4 shrink-0 animate-spin opacity-80" />
        <span className="truncate">
          {label}: <strong>{active.game_title}</strong>
        </span>
      </div>
      <Link
        to={`/forge/${active.game_id}`}
        className="gf-text-accent shrink-0 text-xs font-semibold underline-offset-2 hover:underline"
      >
        {t('activeRunReturn')}
      </Link>
    </div>
  )
}
