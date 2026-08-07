import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { UsageBreakdownItem } from '@/api/usage-breakdown'
import { useT } from '@/i18n/use-t'

const CHART_FONT = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif'

type Props = {
  items: UsageBreakdownItem[]
}

function fmtUsd(n: number) {
  return `$${n.toFixed(2)}`
}

export function UsageBreakdownChart({ items }: Props) {
  const t = useT()
  const chartData = items.map((it) => ({
    name: it.title.length > 8 ? `${it.title.slice(0, 8)}…` : it.title,
    input: it.input_tokens,
    output: it.output_tokens,
    cost: it.estimated_cost_usd,
    game_id: it.game_id,
  }))

  if (items.length === 0) {
    return <p className="text-sm gf-page-muted">{t('usageBreakdownEmpty')}</p>
  }

  return (
    <div className="space-y-4">
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 11, fontFamily: CHART_FONT }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11, fontFamily: CHART_FONT }}
              axisLine={false}
              tickLine={false}
              width={48}
            />
            <Tooltip
              contentStyle={{
                background: '#12151a',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 12,
                fontFamily: CHART_FONT,
                color: '#fff',
              }}
            />
            <Bar dataKey="input" name="input" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
            <Bar dataKey="output" name="output" fill="#38bdf8" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="overflow-x-auto rounded-xl ring-1 ring-[var(--gf-border)]">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--gf-border)] bg-black/[0.03] font-mono text-[10px] tracking-wider gf-page-muted uppercase">
              <th className="px-3 py-2">{t('usageBreakdownGame')}</th>
              <th className="px-3 py-2">{t('usageBreakdownTokens')}</th>
              <th className="px-3 py-2">{t('usageBreakdownCost')}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.game_id} className="border-b border-[var(--gf-border)] last:border-0">
                <td className="px-3 py-2">
                  <Link to={`/forge/${it.game_id}`} className="gf-text-accent hover:underline">
                    {it.title}
                  </Link>
                </td>
                <td className="px-3 py-2 gf-page-muted">
                  {it.input_tokens.toLocaleString()} / {it.output_tokens.toLocaleString()}
                </td>
                <td className="px-3 py-2 gf-text-accent">{fmtUsd(it.estimated_cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

type TrendProps = {
  data: { date: string; page_views: number; play_starts: number }[]
}

export function AnalyticsTrendChart({ data }: TrendProps) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 10, fontFamily: CHART_FONT }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 11, fontFamily: CHART_FONT }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: '#12151a',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 12,
              fontFamily: CHART_FONT,
              color: '#fff',
            }}
          />
          <Line type="monotone" dataKey="page_views" stroke="#2dd4bf" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="play_starts" stroke="#38bdf8" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
