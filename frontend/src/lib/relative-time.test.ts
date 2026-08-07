import { describe, expect, it } from 'vitest'
import { formatRelativeTime } from './relative-time'

describe('formatRelativeTime', () => {
  const now = new Date('2026-08-06T12:00:00.000Z').getTime()

  it('minutes / hours (zh)', () => {
    expect(formatRelativeTime('2026-08-06T11:45:00.000Z', 'zh', now)).toBe('15 分钟前')
    expect(formatRelativeTime('2026-08-06T09:00:00.000Z', 'zh', now)).toBe('3 小时前')
  })

  it('minutes / hours (en)', () => {
    expect(formatRelativeTime('2026-08-06T11:45:00.000Z', 'en', now)).toBe('15m ago')
    expect(formatRelativeTime('2026-08-06T09:00:00.000Z', 'en', now)).toBe('3h ago')
  })
})
