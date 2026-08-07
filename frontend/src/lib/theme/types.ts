import type { WorkshopDesignRef } from './design-prompts'

/** 三色主题：主色 / 辅色 / 页面浅底（仅存浏览器 localStorage，与账号无关） */

export type ThemeColors = {
  /** 强调色：导航高亮、链接、边框光晕 */
  primary: string
  /** 渐变第二色：主按钮、Logo */
  secondary: string
  /** 页面浅底（games / forge / settings 主内容区） */
  background: string
}

export type ThemeGlow = 'off' | 'soft' | 'strong'

export type ThemeSettings = {
  /** 预设 id，或 `custom` 表示用户自行调整三色 */
  presetId: string
  colors: ThemeColors
  /** 主按钮渐变角度（deg） */
  gradientAngle: number
  /** 动态背景光斑（侧栏/壳层，非整页暗色） */
  dynamicBackground: boolean
  glow: ThemeGlow
  /** 本地 schema；升级时迁移为浅色工坊预设 */
  schemaVersion?: number
}

export type ThemePreset = {
  id: string
  name: string
  nameEn: string
  style: WorkshopDesignRef
  colors: ThemeColors
  gradientAngle?: number
}
