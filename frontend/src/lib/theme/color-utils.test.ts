import { describe, expect, it } from 'vitest'
import { hexToRgb, normalizeHex, sanitizeThemeColors } from './color-utils'

describe('color-utils', () => {
  it('normalizes 3 and 6 digit hex', () => {
    expect(normalizeHex('#abc')).toBe('#AABBCC')
    expect(normalizeHex('#00f0ff')).toBe('#00F0FF')
    expect(normalizeHex('bad')).toBeNull()
    expect(normalizeHex('#GGGGGG')).toBeNull()
  })

  it('parses rgb components', () => {
    expect(hexToRgb('#00F0FF')).toEqual({ r: 0, g: 240, b: 255 })
  })

  it('sanitizes invalid persisted colors back to fallback', () => {
    expect(
      sanitizeThemeColors(
        { primary: '#GGGGGG', secondary: '#abc', background: '#F4F6FA' },
        { primary: '#2563EB', secondary: '#60A5FA', background: '#F4F6FA' },
      ),
    ).toEqual({
      primary: '#2563EB',
      secondary: '#AABBCC',
      background: '#F4F6FA',
    })
  })
})
