import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { applyTheme } from '@/lib/theme/apply-theme'
import { normalizeHex } from '@/lib/theme/color-utils'
import { DEFAULT_THEME_SETTINGS, migrateThemeSettings, presetById, settingsFromPreset } from '@/lib/theme/presets'
import { THEME_SCHEMA_VERSION } from '@/lib/theme/design-prompts'
import type { ThemeColors, ThemeGlow, ThemeSettings } from '@/lib/theme/types'

type ThemeState = {
  settings: ThemeSettings
  applyPreset: (presetId: string) => void
  setCustomColors: (colors: Partial<ThemeColors>) => void
  setGradientAngle: (angle: number) => void
  setDynamicBackground: (on: boolean) => void
  setGlow: (glow: ThemeGlow) => void
  resetTheme: () => void
}

function commit(settings: ThemeSettings) {
  applyTheme(settings)
  return settings
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      settings: DEFAULT_THEME_SETTINGS,

      applyPreset: (presetId) => {
        const preset = presetById(presetId)
        if (!preset) return
        const next = commit({
          ...settingsFromPreset(preset),
          dynamicBackground: get().settings.dynamicBackground,
          glow: get().settings.glow,
        })
        set({ settings: next })
      },

      setCustomColors: (partial) => {
        const cur = get().settings
        const nextColors = { ...cur.colors }
        let changed = false
        for (const [key, value] of Object.entries(partial) as [keyof ThemeColors, string][]) {
          const normalized = normalizeHex(value)
          if (!normalized) continue
          if (nextColors[key] !== normalized) {
            nextColors[key] = normalized
            changed = true
          }
        }
        if (!changed) return
        const next = commit({
          ...cur,
          presetId: 'custom',
          colors: nextColors,
          schemaVersion: THEME_SCHEMA_VERSION,
        })
        set({ settings: next })
      },

      setGradientAngle: (angle) => {
        const next = commit({ ...get().settings, gradientAngle: angle, presetId: 'custom' })
        set({ settings: next })
      },

      setDynamicBackground: (on) => {
        const next = commit({ ...get().settings, dynamicBackground: on })
        set({ settings: next })
      },

      setGlow: (glow) => {
        const next = commit({ ...get().settings, glow })
        set({ settings: next })
      },

      resetTheme: () => {
        const next = commit({ ...DEFAULT_THEME_SETTINGS })
        set({ settings: next })
      },
    }),
    {
      name: 'gf-theme',
      partialize: (s) => ({ settings: s.settings }),
      merge: (persisted, current) => {
        const p = persisted as { settings?: ThemeSettings } | undefined
        return {
          ...current,
          settings: migrateThemeSettings(p?.settings),
        }
      },
      onRehydrateStorage: () => (state) => {
        if (state) applyTheme(migrateThemeSettings(state.settings))
      },
    },
  ),
)
