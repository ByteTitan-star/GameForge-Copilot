import { beforeEach, describe, expect, it } from 'vitest'
import { DEFAULT_THEME_SETTINGS, migrateThemeSettings } from '@/lib/theme/presets'
import { useThemeStore } from '@/stores/theme-store'

describe('theme-store custom colors', () => {
  beforeEach(() => {
    useThemeStore.setState({ settings: { ...DEFAULT_THEME_SETTINGS } })
  })

  it('rejects invalid custom colors', () => {
    const before = useThemeStore.getState().settings.colors.primary
    useThemeStore.getState().setCustomColors({ primary: '#GGGGGG' })
    expect(useThemeStore.getState().settings.colors.primary).toBe(before)
  })

  it('normalizes valid hex before persisting', () => {
    useThemeStore.getState().setCustomColors({ primary: '#abc' })
    expect(useThemeStore.getState().settings.colors.primary).toBe('#AABBCC')
    expect(useThemeStore.getState().settings.presetId).toBe('custom')
  })
})

describe('migrateThemeSettings', () => {
  it('repairs invalid colors loaded from storage', () => {
    const migrated = migrateThemeSettings({
      ...DEFAULT_THEME_SETTINGS,
      presetId: 'custom',
      colors: {
        primary: '#GGGGGG',
        secondary: '#60A5FA',
        background: '#F4F6FA',
      },
    })
    expect(migrated.colors.primary).toBe(DEFAULT_THEME_SETTINGS.colors.primary)
    expect(migrated.colors.secondary).toBe('#60A5FA')
  })
})
