import { describe, expect, it, vi } from 'vitest'
import { WSEventType } from '@/api/enums'
import { buildMockRunTimeline, playMockTimeline } from './mock'

describe('WS mock 事件回放', () => {
  it('时间线含 hitl_wait', () => {
    const steps = buildMockRunTimeline('run-1', 'g-1', '测试游戏')
    expect(steps.some((s) => s.event.type === WSEventType.hitl_wait)).toBe(true)
  })

  it('playMockTimeline 按序回调', async () => {
    vi.useFakeTimers()
    const seen: string[] = []
    playMockTimeline(
      [
        { delayMs: 10, event: { type: WSEventType.phase_start, payload: { phase: 'plan' } } },
        { delayMs: 10, event: { type: WSEventType.hitl_wait, payload: { node: 'x' } } },
      ],
      'run-x',
      (ev) => seen.push(ev.type),
    )
    await vi.advanceTimersByTimeAsync(30)
    expect(seen).toEqual([WSEventType.phase_start, WSEventType.hitl_wait])
    vi.useRealTimers()
  })
})
