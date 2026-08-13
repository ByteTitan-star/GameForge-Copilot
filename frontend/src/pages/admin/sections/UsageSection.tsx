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

  // top 用户月 token 总量，占比相对最大值归一化（最活跃用户满格）
  const topUsers = usage.data?.top_users ?? []
  const maxTokens = topUsers.reduce(
    (m, u) => Math.max(m, u.month_input_tokens + u.month_output_tokens),
    0,
  )

  if (!token) return null

  if (usage.isLoading) {
    return (
      <div className="space-y-5">
        <div className="gf-page-muted flex items-center gap-2 text-sm">
          <Loader2 className="h-4 w-4 animate-spin" /> {t('adminLoadingUsage')}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="gf-admin-card space-y-4 rounded-xl p-5">
        <UsageChart data={chart} tone="light" />
        <div>
          <p className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
            {t('adminTopUsers')}
          </p>
          <ul className="mt-2 space-y-1.5">
            {topUsers.map((u, i) => {
              const tokens = u.month_input_tokens + u.month_output_tokens
              const ratio = maxTokens > 0 ? tokens / maxTokens : 0
              return (
                <li
                  key={u.user_id}
                  className="rounded-lg border border-[var(--gf-border)] bg-[var(--gf-surface)] px-3 py-2 text-sm"
                >
                  <div className="flex items-center gap-2.5">
                    <span
                      className="gf-page-muted grid h-5 w-5 shrink-0 place-items-center rounded-md text-[11px] font-semibold tabular-nums"
                      style={{ backgroundColor: 'rgba(var(--gf-primary-rgb), 0.1)' }}
                    >
                      {i + 1}
                    </span>
                    <span className="text-[var(--gf-text)]">{u.email}</span>
                    <span className="gf-page-muted ml-auto font-mono text-xs tabular-nums">
                      {tokens.toLocaleString()} tok · {u.calls} calls
                    </span>
                  </div>
                  <div
                    className="mt-2 h-1.5 overflow-hidden rounded-full"
                    style={{ backgroundColor: 'rgba(var(--gf-text), 0.06)' }}
                  >
                    <div
                      className="h-full rounded-full transition-[width] duration-500"
                      style={{
                        width: `${Math.max(ratio * 100, ratio > 0 ? 4 : 0)}%`,
                        backgroundColor: 'rgba(var(--gf-primary-rgb), 0.5)',
                      }}
                    />
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}
