import { useId } from 'react'
import { useT } from '@/i18n/use-t'

/**
 * Convix 风弧形仪表盘。40 个 tick 跨 180°（从 π 到 2π，上半圆），围绕中心 (100,100)；
 * 每个 tick 从半径 70 到 80 的线段，active（前 round(value/100×40) 个）用 color，其余 #d4d4d8。
 * 中心显示 {value}%。静态 SVG，无自定义动画（尊重 Convix 规约 + 项目 prefers-reduced-motion）。
 *
 * value 会被 clamp 到 [0, 100]。showLabels 时下方一行显示 min/max（如配额池的「已用/总量」）。
 */
const VIEW_W = 200
const VIEW_H = 120
const CENTER = { x: 100, y: 100 }
const R_OUTER = 80
const R_INNER = 70
const TICKS = 40

function polar(angle: number, r: number) {
  return {
    x: CENTER.x + r * Math.cos(angle),
    y: CENTER.y + r * Math.sin(angle),
  }
}

type Props = {
  /** 0-100，超出会被 clamp */
  value: number
  /** active tick 颜色，默认 admin 橙 */
  color?: string
  showLabels?: boolean
  min?: string
  max?: string
}

export function Gauge({ value, color = '#ef4d23', showLabels = false, min, max }: Props) {
  const t = useT()
  const titleId = useId()
  const clamped = Math.max(0, Math.min(100, value))
  const activeCount = Math.round((clamped / 100) * TICKS)

  // 角度从 π（左）扫到 2π（右），共 180°；40 个 tick 均匀分布。
  const ticks = Array.from({ length: TICKS }, (_, i) => {
    const angle = Math.PI + (i / (TICKS - 1)) * Math.PI
    const outer = polar(angle, R_OUTER)
    const inner = polar(angle, R_INNER)
    return { x1: outer.x, y1: outer.y, x2: inner.x, y2: inner.y, active: i < activeCount }
  })

  return (
    <div className="mx-auto w-full" style={{ maxWidth: 260 }}>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="w-full"
        role="img"
        aria-labelledby={titleId}
      >
        <title id={titleId}>{t('adminGaugeValue', { value: clamped })}</title>
        {ticks.map((tk, i) => (
          <line
            key={i}
            x1={tk.x1}
            y1={tk.y1}
            x2={tk.x2}
            y2={tk.y2}
            stroke={tk.active ? color : '#d4d4d8'}
            strokeWidth={2.5}
            strokeLinecap="round"
          />
        ))}
        <text x={CENTER.x} y={105} textAnchor="middle" fontSize={22} fontWeight={600} fill="#0f172a">
          {clamped}%
        </text>
      </svg>
      {showLabels ? (
        <div className="mt-1 flex justify-between text-[11px] text-neutral-500">
          <span>{min}</span>
          <span>{max}</span>
        </div>
      ) : null}
    </div>
  )
}
