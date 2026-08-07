import { useThemeStore } from '@/stores/theme-store'

/** 全屏动态光斑背景，颜色跟随当前主题 CSS 变量 */
export function ThemeBackground() {
  const on = useThemeStore((s) => s.settings.dynamicBackground)
  if (!on) return null

  return (
    <div className="gf-theme-bg pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden>
      <div className="gf-theme-orb gf-theme-orb-a" />
      <div className="gf-theme-orb gf-theme-orb-b" />
      <div className="gf-theme-orb gf-theme-orb-c" />
      <div className="gf-theme-grid" />
    </div>
  )
}
