import { contrastTextOn, hexToRgb, normalizeHex, relativeLuminance } from './color-utils'
import { presetById } from './presets'
import type { ThemeSettings } from './types'

const ROOT = () => document.documentElement

export function applyTheme(settings: ThemeSettings): void {
  const primary = normalizeHex(settings.colors.primary) ?? '#2563EB'
  const secondary = normalizeHex(settings.colors.secondary) ?? '#60A5FA'
  const background = normalizeHex(settings.colors.background) ?? '#F4F6FA'
  const p = hexToRgb(primary)!
  const s = hexToRgb(secondary)!
  const b = hexToRgb(background)!
  const btnText = contrastTextOn(primary, secondary)
  const angle = settings.gradientAngle
  const preset = presetById(settings.presetId)
  const shellStyle = preset?.style ?? 'forma'
  const lightCanvas = relativeLuminance(background) >= 0.72

  const el = ROOT()
  el.style.setProperty('--gf-primary', primary)
  el.style.setProperty('--gf-secondary', secondary)
  el.style.setProperty('--gf-bg', background)
  el.style.setProperty('--gf-primary-rgb', `${p.r}, ${p.g}, ${p.b}`)
  el.style.setProperty('--gf-secondary-rgb', `${s.r}, ${s.g}, ${s.b}`)
  el.style.setProperty('--gf-bg-rgb', `${b.r}, ${b.g}, ${b.b}`)
  el.style.setProperty('--gf-gradient-angle', `${angle}deg`)
  el.style.setProperty('--gf-btn-text', btnText)
  el.style.setProperty(
    '--gf-text',
    lightCanvas ? '#0F172A' : 'rgba(255, 255, 255, 0.92)',
  )
  el.style.setProperty(
    '--gf-text-muted',
    lightCanvas ? '#475569' : 'rgba(255, 255, 255, 0.62)',
  )
  el.style.setProperty('--gf-surface', lightCanvas ? '#FFFFFF' : 'rgba(255, 255, 255, 0.06)')
  el.style.setProperty(
    '--gf-border',
    lightCanvas ? 'rgba(15, 23, 42, 0.08)' : `rgba(${p.r}, ${p.g}, ${p.b}, 0.15)`,
  )
  el.style.setProperty(
    '--gf-sidebar-bg',
    lightCanvas ? 'rgba(255, 255, 255, 0.82)' : `rgba(${b.r}, ${b.g}, ${b.b}, 0.95)`,
  )
  el.style.setProperty('--gf-glow-strength', settings.glow === 'off' ? '0' : settings.glow === 'strong' ? '1' : '0.55')
  el.dataset.gfDynamicBg = settings.dynamicBackground ? '1' : '0'
  el.dataset.gfTheme = settings.presetId
  el.dataset.gfStyle = shellStyle
  el.dataset.gfSurface = lightCanvas ? 'light' : 'dark'
}
