import { describe, expect, it, vi } from 'vitest'
import { parseWsEnvelope } from './client'

describe('WS envelope parse', () => {
  it('解析合法 JSON 信封', () => {
    const ev = parseWsEnvelope(
      JSON.stringify({
        type: 'phase_start',
        run_id: 'r1',
        ts: '2026-08-07T00:00:00Z',
        payload: { phase: 'plan' },
      }),
    )
    expect(ev?.type).toBe('phase_start')
    expect(ev?.payload).toEqual({ phase: 'plan' })
  })

  it('非法 JSON 返回 null', () => {
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(parseWsEnvelope('{nope')).toBeNull()
    spy.mockRestore()
  })
})
