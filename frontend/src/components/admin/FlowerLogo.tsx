/**
 * Convix 风橙色 8 瓣花 logo。8 个 r=3.5 圆均匀分布在半径 10 的圆周上（围绕中心 16,16），
 * 中心再一个 r=3.5 圆，viewBox 32×32。固定橙色 #ef4d23（admin 品牌色，不跟随用户主题），
 * 作为 admin 侧边栏品牌标识。
 */
const PETALS: { cx: number; cy: number }[] = [
  { cx: 26.0, cy: 16.0 },
  { cx: 23.071, cy: 23.071 },
  { cx: 16.0, cy: 26.0 },
  { cx: 8.929, cy: 23.071 },
  { cx: 6.0, cy: 16.0 },
  { cx: 8.929, cy: 8.929 },
  { cx: 16.0, cy: 6.0 },
  { cx: 23.071, cy: 8.929 },
]

export function FlowerLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true" focusable="false">
      {PETALS.map((p) => (
        <circle key={`${p.cx}-${p.cy}`} cx={p.cx} cy={p.cy} r={3.5} fill="#ef4d23" />
      ))}
      <circle cx={16} cy={16} r={3.5} fill="#ef4d23" />
    </svg>
  )
}
