import { describe, expect, it } from 'vitest'
import { formatRelativeTime } from './relative-time'

describe('formatRelativeTime', () => {
  const now = new Date('2026-08-06T12:00:00.000Z').getTime()

  it('分钟 / 小时', () => {
    expect(formatRelativeTime('2026-08-06T11:45:00.000Z', now)).toBe('15 分钟前')
    expect(formatRelativeTime('2026-08-06T09:00:00.000Z', now)).toBe('3 小时前')
  })
})
