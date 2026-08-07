import { describe, expect, it } from 'vitest'
import { hexToRgb, normalizeHex } from './color-utils'

describe('color-utils', () => {
  it('normalizes 3 and 6 digit hex', () => {
    expect(normalizeHex('#abc')).toBe('#AABBCC')
    expect(normalizeHex('#00f0ff')).toBe('#00F0FF')
    expect(normalizeHex('bad')).toBeNull()
  })

  it('parses rgb components', () => {
    expect(hexToRgb('#00F0FF')).toEqual({ r: 0, g: 240, b: 255 })
  })
})
