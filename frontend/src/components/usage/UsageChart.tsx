import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useT } from '@/i18n/use-t'

type Point = { name: string; input: number; output: number }

type Props = {
  data: Point[]
  /** light = 浅色卡片（settings 用量看板）；dark = 深色面板（admin，默认） */
  tone?: 'light' | 'dark'
}

/** 中文标签必须显式字体，避免 canvas/svg 回退缺字（项目历史教训） */
const CHART_FONT = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif'

const AXIS = {
  light: { tick: '#64748b', tickMute: '#94a3b8', grid: 'rgba(15,23,42,0.08)', legend: '#64748b' },
  dark: {
    tick: 'rgba(255,255,255,0.55)',
    tickMute: 'rgba(255,255,255,0.45)',
    grid: 'rgba(255,255,255,0.06)',
    legend: 'rgba(255,255,255,0.6)',
  },
}

const TOOLTIP_STYLE = {
  light: { background: '#ffffff', border: '1px solid rgba(15,23,42,0.1)', color: '#0f172a' },
  dark: { background: '#12151a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' },
}

export function UsageChart({ data, tone = 'dark' }: Props) {
  const t = useT()
  const a = AXIS[tone]
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={a.grid} vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: a.tick, fontSize: 12, fontFamily: CHART_FONT }}
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
            contentStyle={{
              ...TOOLTIP_STYLE[tone],
              borderRadius: 12,
              fontFamily: CHART_FONT,
            }}
          />
          <Legend wrapperStyle={{ fontFamily: CHART_FONT, fontSize: 12, color: a.legend }} />
          <Bar dataKey="input" name={t('usageInputTokens')} fill="#2dd4bf" radius={[4, 4, 0, 0]} />
          <Bar dataKey="output" name={t('usageOutputTokens')} fill="#38bdf8" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
