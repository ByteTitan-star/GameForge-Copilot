/**
 * 柱状图十字准星 cursor：贯穿绘图区的垂直虚线。
 *
 * 为什么独立组件：UsageChart（admin 系统用量）与 UsageBreakdownChart（settings
 * 用量看板）都是柱状图，cursor 体验需对齐折线图的 dashed 准星，避免两张柱状图
 * 风格割裂。recharts 在挂载 cursor 时注入当前类目的绘图矩形（x/y/width/height）
 * 与 offset（绘图区边界 top/bottom），按类目中线画一条贯穿顶底的虚线。
 */
export function BarCrosshair({
  x = 0,
  y = 0,
  width = 0,
  height = 0,
  offset,
  color,
}: {
  x?: number
  y?: number
  width?: number
  height?: number
  offset?: { top?: number; bottom?: number }
  color: string
}) {
  const cx = x + width / 2
  const top = offset?.top ?? y
  const bottom = offset?.bottom ?? y + height
  return (
    <line
      x1={cx}
      y1={top}
      x2={cx}
      y2={bottom}
      stroke={color}
      strokeWidth={1}
      strokeDasharray="4 4"
    />
  )
}
