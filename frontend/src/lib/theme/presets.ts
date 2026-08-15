import { THEME_SCHEMA_VERSION } from './design-prompts'
import { sanitizeThemeColors } from './color-utils'
import type { ThemePreset, ThemeSettings } from './types'

export const DEFAULT_PRESET_ID = 'forma-glass'

/** 全部预设：浅色页面底 + 参考 UI 壳层风格（不含 Aethera 白底极简整页） */
export const THEME_PRESETS: ThemePreset[] = [
  {
    id: 'forma-glass',
    name: 'Forma 玻璃',
    nameEn: 'Forma Glass',
    style: 'forma',
    colors: { primary: '#2563EB', secondary: '#60A5FA', background: '#F4F6FA' },
    gradientAngle: 135,
  },
  {
    id: 'atelier-forge',
    name: 'Atelier 电影',
    nameEn: 'Atelier Forge',
    style: 'atelier',
    colors: { primary: '#171717', secondary: '#525252', background: '#F6F5F1' },
    gradientAngle: 130,
  },
  {
    id: 'taskly-glass',
    name: 'Taskly 液态',
    nameEn: 'Taskly Liquid',
    style: 'taskly',
    colors: { primary: '#0084FF', secondary: '#60B1FF', background: '#FAFBFC' },
    gradientAngle: 140,
  },
  {
    id: 'arcade-neon',
    name: '街机霓虹',
    nameEn: 'Arcade Neon',
    style: 'arcade',
    colors: { primary: '#0891B2', secondary: '#7C3AED', background: '#F0F9FF' },
    gradientAngle: 135,
  },
  {
    id: 'sunset-arcade',
    name: '落日街机',
    nameEn: 'Sunset Arcade',
    style: 'arcade',
    colors: { primary: '#EA580C', secondary: '#FB923C', background: '#FFF7ED' },
    gradientAngle: 120,
  },
  {
    id: 'forest-pixel',
    name: '像素森林',
    nameEn: 'Forest Pixel',
    style: 'arcade',
    colors: { primary: '#059669', secondary: '#34D399', background: '#F0FDF4' },
    gradientAngle: 140,
  },
]

export const DEFAULT_THEME_SETTINGS: ThemeSettings = {
  presetId: DEFAULT_PRESET_ID,
  colors: THEME_PRESETS[0].colors,
  gradientAngle: 135,
  dynamicBackground: true,
  glow: 'soft',
  schemaVersion: THEME_SCHEMA_VERSION,
}

export function presetById(id: string): ThemePreset | undefined {
  return THEME_PRESETS.find((p) => p.id === id)
}

export function settingsFromPreset(preset: ThemePreset): ThemeSettings {
  return {
    presetId: preset.id,
    colors: { ...preset.colors },
    gradientAngle: preset.gradientAngle ?? 135,
    dynamicBackground: true,
    glow: 'soft',
    schemaVersion: THEME_SCHEMA_VERSION,
  }
}

export function migrateThemeSettings(raw: ThemeSettings | undefined): ThemeSettings {
  if (!raw || (raw.schemaVersion ?? 1) < THEME_SCHEMA_VERSION) {
    return { ...DEFAULT_THEME_SETTINGS }
  }
  return {
    ...DEFAULT_THEME_SETTINGS,
    ...raw,
    colors: sanitizeThemeColors(raw.colors, DEFAULT_THEME_SETTINGS.colors),
    schemaVersion: THEME_SCHEMA_VERSION,
  }
}
