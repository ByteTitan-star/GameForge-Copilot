import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { analyticsApi } from '@/api/analytics'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { AdminTable } from '@/components/admin/AdminTable'
import { AnalyticsTrendChart } from '@/components/usage/UsageBreakdown'

/** admin 橙色 hex，喂给 recharts（绕过 useThemeColors 读 <html> 的限制） */
const ORANGE = '#ef4d23'
const ORANGE_2 = '#f97316'

export function AnalyticsSection() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)

  const q = useQuery({
    queryKey: ['admin', 'analytics'],
    queryFn: () => analyticsApi.getTop(token!),
  })

  if (!token) return null

  const data = q.data

  return (
    <div className="space-y-5">
      {q.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-neutral-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('loading')}
        </p>
      ) : null}
      {q.isError ? (
        <p className="flex items-center gap-2 text-sm text-rose-500">{t('loadFailed')}</p>
      ) : null}
      {data ? (
        <>
          <AdminTable
            headers={[t('usageBreakdownGame'), 'slug', t('adminAnalyticsPlays')]}
            loading={false}
            empty={t('usageBreakdownEmpty')}
            rows={data.top_games.map((g) => (
              <tr key={g.game_id} className="border-t border-[var(--gf-border)]">
                <td className="px-4 py-3 text-sm">{g.title}</td>
                <td className="gf-text-accent px-4 py-3 font-mono text-xs">{g.slug ?? '—'}</td>
                <td className="gf-page-muted px-4 py-3 font-mono text-sm">
                  {g.play_count.toLocaleString()}
                </td>
              </tr>
            ))}
          />
          <section className="gf-admin-card rounded-xl p-4">
            <p className="gf-page-muted mb-3 text-[11px] font-medium uppercase tracking-wider">
              {t('adminAnalyticsTrend')}
            </p>
            <AnalyticsTrendChart data={data.trend} tone="light" primaryHex={ORANGE} secondaryHex={ORANGE_2} />
          </section>
        </>
      ) : null}
    </div>
  )
}
