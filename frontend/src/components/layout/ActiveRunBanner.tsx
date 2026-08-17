import { useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Loader2, X } from 'lucide-react'
import { RunStatus } from '@/api/enums'
import { useActiveRuns } from '@/hooks/use-active-runs'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { isTrialUser } from '@/lib/trial'

const DISMISS_KEY = 'gf-dismissed-active-runs'

function readDismissed(): Set<string> {
  try {
    const raw = localStorage.getItem(DISMISS_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((item): item is string => typeof item === 'string'))
  } catch {
    return new Set()
  }
}

function persistDismissed(ids: Set<string>) {
  try {
    localStorage.setItem(DISMISS_KEY, JSON.stringify([...ids]))
  } catch {
    /* ignore quota errors */
  }
}

export function ActiveRunBanner() {
  const t = useT()
  const location = useLocation()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const { data } = useActiveRuns(token)
  const trial = isTrialUser(user)
  const [dismissed, setDismissed] = useState<Set<string>>(() => readDismissed())

  const active = useMemo(
    () =>
      (data?.data ?? []).find(
        (r) => r.status === RunStatus.running || r.status === RunStatus.paused,
      ),
    [data?.data],
  )

  if (!token || trial || !active) return null
  if (location.pathname === `/forge/${active.game_id}`) return null
  if (dismissed.has(active.run_id)) return null

  const label =
    active.status === RunStatus.paused ? t('activeRunPausedBanner') : t('activeRunBanner')

  function dismiss() {
    const next = new Set(dismissed)
    next.add(active!.run_id)
    setDismissed(next)
    persistDismissed(next)
  }

  return (
    <div
      role="status"
      className="gf-active-run-toast flex items-start gap-3 rounded-xl px-3.5 py-3 text-sm"
    >
      <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin opacity-80" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="leading-snug">
          {label}: <strong>{active.game_title}</strong>
        </p>
        <Link
          to={`/forge/${active.game_id}`}
          className="gf-text-accent mt-1 inline-block text-xs font-semibold underline-offset-2 hover:underline"
        >
          {t('activeRunReturn')}
        </Link>
      </div>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t('close')}
        className="gf-interactive grid h-7 w-7 shrink-0 place-items-center rounded-md text-black/45 transition hover:bg-black/[0.05] hover:text-black/75"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  )
}
