import { useQuery } from '@tanstack/react-query'
import { meApi } from '@/api/me'
import { UsageChart } from '@/components/usage/UsageChart'
import { useAuthStore } from '@/stores/auth-store'

function fmt(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

export function UsagePanel() {
  const token = useAuthStore((s) => s.access_token)
  const q = useQuery({
    queryKey: ['me-usage'],
    enabled: Boolean(token),
    queryFn: () => meApi.usage(token!),
  })

  const d = q.data
  const chartData = d
    ? [
        { name: '今日', input: d.today.input_tokens, output: d.today.output_tokens },
        { name: '本月', input: d.month.input_tokens, output: d.month.output_tokens },
        { name: '累计', input: d.total.input_tokens, output: d.total.output_tokens },
      ]
    : []

  return (
    <section className="space-y-4 rounded-2xl border border-white/[0.08] bg-[#12151a] p-5">
      <div>
        <h2 className="text-lg text-white/90">用量看板</h2>
        <p className="mt-1 text-sm text-white/40">真实 token 用量（mock 数据对齐 `/me/usage` schema）</p>
      </div>

      {q.isLoading ? <p className="text-sm text-white/40">加载中…</p> : null}
      {q.isError ? <p className="text-sm text-red-300">用量加载失败</p> : null}

      {d ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              ['今日调用', String(d.today.calls)],
              ['本月调用', String(d.month.calls)],
              ['日配额已用', fmt(d.quota.daily_used)],
              ['日配额剩余', fmt(d.quota.remaining)],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl bg-black/25 p-3 ring-1 ring-white/[0.04]">
                <p className="font-mono text-[10px] tracking-wider text-white/35 uppercase">{k}</p>
                <p className="mt-1 text-xl text-teal-200/90">{v}</p>
              </div>
            ))}
          </div>
          <UsageChart data={chartData} />
          <p className="font-mono text-[11px] text-white/30">
            日限额 {fmt(d.quota.daily_token_limit)} · 今日 in/out{' '}
            {fmt(d.today.input_tokens)}/{fmt(d.today.output_tokens)}
          </p>
        </>
      ) : null}
    </section>
  )
}
