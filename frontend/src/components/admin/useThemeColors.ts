import { useEffect, useState } from 'react'
import { useThemeStore } from '@/stores/theme-store'

/**
 * 读取当前主题计算后的 primary / secondary hex，供 recharts 使用。
 *
 * 为什么需要：recharts 的 <Bar fill> / <defs><linearGradient stopColor> 在部分
 * 浏览器里对 CSS 变量透传不稳定（setAttribute 可能丢弃 var(...)）。最稳的做法
 * 是把计算后的 hex 直接喂给 recharts。--gf-primary / --gf-secondary 由 applyTheme
 * 写成 hex 字符串（如 #2563eb），可直接用。
 *
 * 刷新时机：主题 store 任一变更（preset / 自定义色 / 角度）→ applyTheme 重写 inline
 * style → 此 hook 订阅 useThemeStore 触发重读。SSR / jest 下 getComputedStyle 不可
 * 用，返回 fallback。
 */
const FALLBACK = { primary: '#2563eb', secondary: '#60a5fa' }

function readColors(): { primary: string; secondary: string } {
  if (typeof window === 'undefined') return FALLBACK
  const root = document.documentElement
  const primary = getComputedStyle(root).getPropertyValue('--gf-primary').trim()
  const secondary = getComputedStyle(root).getPropertyValue('--gf-secondary').trim()
  return {
    primary: primary || FALLBACK.primary,
    secondary: secondary || FALLBACK.secondary,
  }
}

export function useThemeColors() {
  // 依赖 settings 引用：主题任一变更都会产生新的 settings 对象（commit 返回新对象）
  const settings = useThemeStore((s) => s.settings)
  const [colors, setColors] = useState(readColors)

  useEffect(() => {
    // applyTheme 同步执行，下一帧读 computed 确保生效；settings 变更即重读
    setColors(readColors())
  }, [settings])

  return colors
}
