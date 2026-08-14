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
import { useThemeColors } from '@/components/admin/useThemeColors'
import { BarCrosshair } from './BarCrosshair'

type Point = { name: string; input: number; output: number }

type Props = {
  data: Point[]
  /** light = 浅色卡片（settings 用量看板）；dark = 深色面板（admin，默认） */
  tone?: 'light' | 'dark'
  /** 显式指定主/辅色 hex，覆盖主题色。admin 作用域走橙色主题但 useThemeColors 读的是
   * <html> inline style（读不到 .gf-admin !important 覆盖），故 admin 调用处直接传橙色 hex，
   * 避免出现"卡片按钮橙、图表柱蓝/绿"的割裂。主站不传，继续走用户主题色。 */
  primaryHex?: string
  secondaryHex?: string
}

/** 中文标签必须显式字体，避免 canvas/svg 回退缺字（项目历史教训） */
const CHART_FONT = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif'

const AXIS = {
  light: {
    tick: '#64748b',
    tickMute: '#94a3b8',
    grid: 'rgba(15,23,42,0.08)',
    legend: '#64748b',
    cursor: 'rgba(15,23,42,0.22)',
  },
  dark: {
    tick: 'rgba(255,255,255,0.55)',
    tickMute: 'rgba(255,255,255,0.45)',
    grid: 'rgba(255,255,255,0.06)',
    legend: 'rgba(255,255,255,0.6)',
    cursor: 'rgba(255,255,255,0.28)',
  },
}

const TOOLTIP_STYLE = {
  light: { background: '#ffffff', border: '1px solid rgba(15,23,42,0.08)', color: '#0f172a' },
  dark: { background: '#12151a', border: '1px solid rgba(255,255,255,0.1)', color: '#fff' },
}

export function UsageChart({ data, tone = 'dark', primaryHex, secondaryHex }: Props) {
  const t = useT()
  const a = AXIS[tone]
  // 用品牌色 hex 喂 recharts（input→primary、output→secondary），跟随用户主题；
  // primaryHex/secondaryHex 显式传入时覆盖（admin 橙色旁路）
  const themeColors = useThemeColors()
  const primary = primaryHex ?? themeColors.primary
  const secondary = secondaryHex ?? themeColors.secondary
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="28%">
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
            cursor={<BarCrosshair color={a.cursor} />}
            contentStyle={{
              ...TOOLTIP_STYLE[tone],
              borderRadius: 12,
              boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
              fontFamily: CHART_FONT,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontFamily: CHART_FONT, fontSize: 12, color: a.legend }} />
          <Bar dataKey="input" name={t('usageInputTokens')} fill={primary} radius={[6, 6, 0, 0]} maxBarSize={48} />
          <Bar dataKey="output" name={t('usageOutputTokens')} fill={secondary} radius={[6, 6, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
