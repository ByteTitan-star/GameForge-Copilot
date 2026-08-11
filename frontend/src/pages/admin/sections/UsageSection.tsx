import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { UsageChart } from '@/components/usage/UsageChart'

export function UsageSection() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)

  const usage = useQuery({
    queryKey: ['admin', 'usage'],
    queryFn: () => adminApi.usage(token!),
  })

  const chart = useMemo(() => {
    const s = usage.data?.system
    if (!s) return []
    return [
      { name: t('usageToday'), input: s.today.input_tokens, output: s.today.output_tokens },
      { name: t('usageMonth'), input: s.month.input_tokens, output: s.month.output_tokens },
      { name: t('usageTotal'), input: s.total.input_tokens, output: s.total.output_tokens },
    ]
  }, [usage.data, t])

  if (!token) return null

  if (usage.isLoading) {
    return (
      <div className="gf-page-muted flex items-center gap-2 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" /> {t('adminLoadingUsage')}
      </div>
    )
  }

  return (
    <div className="gf-glass space-y-4 rounded-2xl p-5">
      <h2 className="text-lg text-[var(--gf-text)]">{t('adminUsageTitle')}</h2>
      <UsageChart data={chart} />
      <div>
        <p className="gf-page-muted font-mono text-[10px] uppercase tracking-wider">
          {t('adminTopUsers')}
        </p>
        <ul className="mt-2 space-y-1.5">
          {(usage.data?.top_users ?? []).map((u) => (
            <li
              key={u.user_id}
              className="flex justify-between rounded-xl border border-[var(--gf-border)] bg-[var(--gf-surface)] px-3 py-2 text-sm"
            >
              <span className="text-[var(--gf-text)]">{u.email}</span>
              <span className="gf-page-muted font-mono text-xs">
                {u.month_input_tokens + u.month_output_tokens} tok · {u.calls} calls
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
