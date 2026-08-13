import { describe, expect, it, vi } from 'vitest'
import { RunPhase, RunStatus, WSEventType } from '@/api/enums'
import type { WsEnvelope } from '@/api/ws-types'
import { emptyStagePipeline } from '@/lib/stage-pipeline-state'
import { handleForgeWsEvent, type ForgeEventHandlers } from './forge-events'

function event(type: WSEventType, payload: Record<string, unknown>): WsEnvelope {
  return { type, run_id: 'run-1', ts: '2026-08-13T00:00:00Z', payload }
}

function handlers() {
  const setHitl = vi.fn()
  const setPhase = vi.fn()
  const setBusy = vi.fn()
  const setRunStatus = vi.fn()
  const setPreviewVersion = vi.fn()
  const h: ForgeEventHandlers = {
    setHitl,
    setPhase,
    setBusy,
    setRunStatus,
    setPreviewVersion,
    pushItem: vi.fn(),
    setPreviewUrl: vi.fn(),
    setSideTab: vi.fn(),
    appendMessages: vi.fn(),
    setStagePipeline: vi.fn((update) => update(emptyStagePipeline())),
    gameId: 'game-1',
    runId: 'run-1',
    t: (key) => key,
  }
  return { h, setHitl, setPhase, setBusy, setRunStatus, setPreviewVersion }
}

describe('forge websocket event state', () => {
  it('phase_start 清除旧 HITL 并恢复运行态', () => {
    const { h, setHitl, setPhase, setBusy, setRunStatus } = handlers()
    handleForgeWsEvent(
      event(WSEventType.phase_start, { phase: RunPhase.art, human_label: '选择素材' }),
      h,
    )
    expect(setHitl).toHaveBeenCalledWith(null)
    expect(setPhase).toHaveBeenCalledWith(RunPhase.art)
    expect(setBusy).toHaveBeenCalledWith(true)
    expect(setRunStatus).toHaveBeenCalledWith(RunStatus.running)
  })

  it.each([WSEventType.done, WSEventType.error])('%s 清除旧 HITL', (type) => {
    const { h, setHitl } = handlers()
    const payload =
      type === WSEventType.done
        ? { game_id: 'game-1', version: 1, preview_url: '/draft/game-1/1' }
        : { code: 'RUN_FAILED', message: 'failed', fatal: true }
    handleForgeWsEvent(event(type, payload), h)
    expect(setHitl).toHaveBeenCalledWith(null)
  })

  it('build_done 和 done 同步预览版本', () => {
    const { h, setPreviewVersion } = handlers()
    handleForgeWsEvent(event(WSEventType.build_done, { version: 3, preview_url: '/draft/game-1/3' }), h)
    expect(setPreviewVersion).toHaveBeenCalledWith(3)
    handleForgeWsEvent(event(WSEventType.done, { game_id: 'game-1', version: 3 }), h)
    expect(setPreviewVersion).toHaveBeenCalledWith(3)
  })
})
