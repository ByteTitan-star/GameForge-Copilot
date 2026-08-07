import { describe, expect, it } from 'vitest'
import { applyTheme } from './apply-theme'
import { DEFAULT_THEME_SETTINGS } from './presets'

describe('applyTheme', () => {
  it('sets light workshop CSS variables on documentElement', () => {
    applyTheme(DEFAULT_THEME_SETTINGS)
    const style = document.documentElement.style
    expect(style.getPropertyValue('--gf-primary').trim()).toBe('#2563EB')
    expect(style.getPropertyValue('--gf-bg').trim()).toBe('#F4F6FA')
    expect(style.getPropertyValue('--gf-text').trim()).toBe('#0F172A')
    expect(document.documentElement.dataset.gfStyle).toBe('forma')
    expect(document.documentElement.dataset.gfSurface).toBe('light')
    expect(document.documentElement.dataset.gfDynamicBg).toBe('1')
  })

  it('reflects custom accent colors', () => {
    applyTheme({
      ...DEFAULT_THEME_SETTINGS,
      presetId: 'custom',
      colors: { primary: '#FF0000', secondary: '#00FF00', background: '#F5F5F5' },
      dynamicBackground: false,
      glow: 'off',
    })
    expect(document.documentElement.style.getPropertyValue('--gf-primary').trim()).toBe('#FF0000')
    expect(document.documentElement.dataset.gfDynamicBg).toBe('0')
  })
})
