import { useQuery } from '@tanstack/react-query'
import { meApi } from '@/api/me'
import { usageBreakdownApi } from '@/api/usage-breakdown'
import { UsageChart } from '@/components/usage/UsageChart'
import { UsageBreakdownChart } from '@/components/usage/UsageBreakdown'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'

function fmt(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export function UsagePanel() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const q = useQuery({
    queryKey: ['me-usage'],
    enabled: Boolean(token),
    queryFn: () => meApi.usage(token!),
  })

  const breakdownQ = useQuery({
    queryKey: ['me-usage-breakdown'],
    enabled: Boolean(token),
    queryFn: () => usageBreakdownApi.get(token!),
  })

  const d = q.data
  const chartData = d
    ? [
        { name: t('usageToday'), input: d.today.input_tokens, output: d.today.output_tokens },
        { name: t('usageMonth'), input: d.month.input_tokens, output: d.month.output_tokens },
        { name: t('usageTotal'), input: d.total.input_tokens, output: d.total.output_tokens },
      ]
    : []

  const quotaLow =
    d && d.quota.daily_token_limit > 0 && d.quota.remaining / d.quota.daily_token_limit < 0.1

  return (
    <section className="gf-glass space-y-4 rounded-2xl p-5">
      <div>
        <h2 className="gf-page-body text-lg">{t('usageTitle')}</h2>
        <p className="mt-1 gf-page-muted text-sm">{t('usageSubtitle')}</p>
      </div>

      {quotaLow ? (
        <p role="status" className="rounded-xl border border-amber-300/40 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {t('usageQuotaWarning')
            .replace('{remaining}', fmt(d!.quota.remaining))
            .replace('{limit}', fmt(d!.quota.daily_token_limit))}
        </p>
      ) : null}

      {q.isLoading ? <p className="gf-page-muted text-sm">{t('loading')}</p> : null}
      {q.isError ? <p className="text-sm text-red-600">{t('usageLoadFailed')}</p> : null}

      {d ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              [t('usageTodayCalls'), String(d.today.calls)],
              [t('usageMonthCalls'), String(d.month.calls)],
              [t('usageDailyUsed'), fmt(d.quota.daily_used)],
              [t('usageDailyRemaining'), fmt(d.quota.remaining)],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-[var(--gf-border)]">
                <p className="font-mono text-[10px] tracking-wider gf-page-muted uppercase">{k}</p>
                <p className="mt-1 text-xl gf-text-accent">{v}</p>
              </div>
            ))}
          </div>
          <UsageChart data={chartData} tone="light" />
          <p className="font-mono text-[11px] gf-page-muted">
            {t('usageDailyLimitLine')
              .replace('{limit}', fmt(d.quota.daily_token_limit))
              .replace('{in}', fmt(d.today.input_tokens))
              .replace('{out}', fmt(d.today.output_tokens))}
          </p>
        </>
      ) : null}

      <div className="border-t border-[var(--gf-border)] pt-4">
        <h3 className="gf-page-body text-base">{t('usageBreakdownTitle')}</h3>
        {breakdownQ.isLoading ? <p className="mt-2 gf-page-muted text-sm">{t('loading')}</p> : null}
        {breakdownQ.isError ? (
          <p className="mt-2 text-sm text-red-600">{t('usageLoadFailed')}</p>
        ) : null}
        {breakdownQ.data ? (
          <div className="mt-3">
            <UsageBreakdownChart items={breakdownQ.data.items} tone="light" />
            <p className="mt-2 font-mono text-[11px] gf-page-muted">
              {t('usageBreakdownCost')}: ${breakdownQ.data.total_estimated_cost_usd.toFixed(2)}
            </p>
          </div>
        ) : null}
      </div>
    </section>
  )
}
