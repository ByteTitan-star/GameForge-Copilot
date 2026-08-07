import { useEffect } from 'react'
import { applyTheme } from '@/lib/theme/apply-theme'
import { useThemeStore } from '@/stores/theme-store'

/** 订阅主题 store，确保任意入口修改后立即刷新 CSS 变量 */
export function ThemeBootstrap() {
  const settings = useThemeStore((s) => s.settings)

  useEffect(() => {
    applyTheme(settings)
  }, [settings])

  return null
}
