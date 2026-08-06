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

type Point = { name: string; input: number; output: number }

type Props = {
  data: Point[]
}

/** 中文标签必须显式字体，避免 canvas/svg 回退缺字（项目历史教训） */
const CHART_FONT = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif'

export function UsageChart({ data }: Props) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: 'rgba(255,255,255,0.55)', fontSize: 12, fontFamily: CHART_FONT }}
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
          <Legend wrapperStyle={{ fontFamily: CHART_FONT, fontSize: 12, color: 'rgba(255,255,255,0.6)' }} />
          <Bar dataKey="input" name="输入 tokens" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
          <Bar dataKey="output" name="输出 tokens" fill="#38bdf8" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
