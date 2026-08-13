import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { UsageBreakdownItem } from '@/api/usage-breakdown'
import { useT } from '@/i18n/use-t'
import { useThemeColors } from '@/components/admin/useThemeColors'
import { BarCrosshair } from './BarCrosshair'

const CHART_FONT = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif'

const AXIS = {
  light: {
    tick: '#64748b',
    tickMute: '#94a3b8',
    grid: 'rgba(15,23,42,0.08)',
    cursor: 'rgba(15,23,42,0.22)',
  },
  dark: {
    tick: 'rgba(255,255,255,0.55)',
    tickMute: 'rgba(255,255,255,0.45)',
    grid: 'rgba(255,255,255,0.06)',
    cursor: 'rgba(255,255,255,0.28)',
  },
}

const TOOLTIP_STYLE = {
  light: { background: '#ffffff', border: '1px solid rgba(15,23,42,0.08)', color: '#0f172a' },
  dark: { background: '#12151a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' },
}

type Props = {
  items: UsageBreakdownItem[]
  /** light = 浅色卡片（settings）；dark = 深色面板（admin，默认） */
  tone?: 'light' | 'dark'
}

function fmtUsd(n: number) {
  return `$${n.toFixed(2)}`
}

export function UsageBreakdownChart({ items, tone = 'dark' }: Props) {
  const t = useT()
  const a = AXIS[tone]
  const { primary, secondary } = useThemeColors()
  const chartData = items.map((it) => {
    const title = it.title ?? '-'
    return {
      name: title.length > 8 ? `${title.slice(0, 8)}…` : title,
      input: it.input_tokens,
      output: it.output_tokens,
      cost: it.estimated_usd,
      id: it.id,
    }
  })

  if (items.length === 0) {
    return <p className="text-sm gf-page-muted">{t('usageBreakdownEmpty')}</p>
  }

  return (
    <div className="space-y-4">
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="28%">
            <CartesianGrid stroke={a.grid} vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: a.tick, fontSize: 11, fontFamily: CHART_FONT }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: a.tickMute, fontSize: 11, fontFamily: CHART_FONT }}
              axisLine={false}
              tickLine={false}
              width={48}
            />
            <Tooltip
              cursor={<BarCrosshair color={a.cursor} />}
              contentStyle={{
                ...TOOLTIP_STYLE[tone],
                borderRadius: 12,
                boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
                fontFamily: CHART_FONT,
                fontSize: 12,
              }}
            />
            <Legend wrapperStyle={{ fontFamily: CHART_FONT, fontSize: 12 }} />
            <Bar dataKey="input" name={t('usageInputTokens')} fill={primary} radius={[6, 6, 0, 0]} maxBarSize={48} />
            <Bar dataKey="output" name={t('usageOutputTokens')} fill={secondary} radius={[6, 6, 0, 0]} maxBarSize={48} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="overflow-x-auto rounded-xl ring-1 ring-[var(--gf-border)]">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--gf-border)] bg-[color-mix(in_srgb,var(--gf-text)_3%,transparent)] text-[11px] font-medium tracking-wider gf-page-muted uppercase">
              <th className="px-3 py-2">{t('usageBreakdownGame')}</th>
              <th className="px-3 py-2">{t('usageBreakdownTokens')}</th>
              <th className="px-3 py-2">{t('usageBreakdownCost')}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.id} className="border-b border-[var(--gf-border)] last:border-0">
                <td className="px-3 py-2">
                  <Link to={`/forge/${it.id}`} className="gf-text-accent hover:underline">
                    {it.title ?? '-'}
                  </Link>
                </td>
                <td className="px-3 py-2 gf-page-muted">
                  {it.input_tokens.toLocaleString()} / {it.output_tokens.toLocaleString()}
                </td>
                <td className="px-3 py-2 gf-text-accent">{fmtUsd(it.estimated_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

type TrendProps = {
  data: { date: string; page_views: number; unique_visitors: number }[]
  tone?: 'light' | 'dark'
}

export function AnalyticsTrendChart({ data, tone = 'dark' }: TrendProps) {
  const t = useT()
  const a = AXIS[tone]
  const { primary, secondary } = useThemeColors()
  if (data.length === 0) {
    return <p className="text-sm gf-page-muted">{t('usageNoTrendData')}</p>
  }
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="gf-trend-pv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={primary} stopOpacity={0.3} />
              <stop offset="100%" stopColor={primary} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gf-trend-uv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={secondary} stopOpacity={0.3} />
              <stop offset="100%" stopColor={secondary} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={a.grid} vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: a.tickMute, fontSize: 10, fontFamily: CHART_FONT }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: a.tickMute, fontSize: 11, fontFamily: CHART_FONT }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip
            cursor={{
              stroke: tone === 'light' ? 'rgba(15,23,42,0.2)' : 'rgba(255,255,255,0.2)',
              strokeWidth: 1,
              strokeDasharray: '4 4',
            }}
            contentStyle={{
              ...TOOLTIP_STYLE[tone],
              borderRadius: 12,
              boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
              fontFamily: CHART_FONT,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontFamily: CHART_FONT, fontSize: 12 }} />
          <Area
            type="monotone"
            dataKey="page_views"
            name={t('analyticsPageViews')}
            stroke={primary}
            strokeWidth={2}
            fill="url(#gf-trend-pv)"
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Area
            type="monotone"
            dataKey="unique_visitors"
            name={t('analyticsUniqueVisitors')}
            stroke={secondary}
            strokeWidth={2}
            fill="url(#gf-trend-uv)"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
