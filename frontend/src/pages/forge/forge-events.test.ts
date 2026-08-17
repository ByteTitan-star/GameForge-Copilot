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
  const setRunError = vi.fn()
  const setStagePipeline = vi.fn((update) => update(emptyStagePipeline()))
  const onRunFinished = vi.fn()
  const pushItem = vi.fn()
  const h: ForgeEventHandlers = {
    setHitl,
    setPhase,
    setBusy,
    setRunStatus,
    setPreviewVersion,
    pushItem,
    setPreviewUrl: vi.fn(),
    setSideTab: vi.fn(),
    appendMessages: vi.fn(),
    setStagePipeline,
    setRunError,
    onRunFinished,
    gameId: 'game-1',
    runId: 'run-1',
    t: (key) => key,
  }
  return {
    h,
    setHitl,
    setPhase,
    setBusy,
    setRunStatus,
    setPreviewVersion,
    setPreviewUrl: h.setPreviewUrl,
    setRunError,
    setStagePipeline,
    onRunFinished,
    pushItem,
  }
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

  it('build_done 解析 vite preview token 路径', () => {
    const { h, setPreviewUrl } = handlers()
    handleForgeWsEvent(
      event(WSEventType.build_done, {
        version: 3,
        preview_url: '/preview/tok-abc/game-1/3/',
        build: 'vite',
      }),
      h,
    )
    expect(setPreviewUrl).toHaveBeenCalledWith(
      expect.stringMatching(/\/preview\/tok-abc\/game-1\/3\//),
    )
  })

  it('build_done 和 done 同步预览版本', () => {
    const { h, setPreviewVersion } = handlers()
    handleForgeWsEvent(event(WSEventType.build_done, { version: 3, preview_url: '/draft/game-1/3' }), h)
    expect(setPreviewVersion).toHaveBeenCalledWith(3)
    handleForgeWsEvent(event(WSEventType.done, { game_id: 'game-1', version: 3 }), h)
    expect(setPreviewVersion).toHaveBeenCalledWith(3)
  })

  it('用户取消（CANCELLED）不当作生成失败', () => {
    const { h, setRunStatus, setRunError, setStagePipeline, setPhase, setBusy, pushItem } = handlers()
    handleForgeWsEvent(
      event(WSEventType.error, { code: 'CANCELLED', message: '用户取消', fatal: true }),
      h,
    )
    expect(setRunStatus).toHaveBeenCalledWith('idle')
    expect(setPhase).toHaveBeenCalledWith('idle')
    expect(setBusy).toHaveBeenCalledWith(false)
    expect(setRunError).not.toHaveBeenCalled()
    expect(setStagePipeline).not.toHaveBeenCalled()
    expect(pushItem).toHaveBeenCalledWith(
      expect.objectContaining({ label: 'runCancelled', tone: 'warn' }),
    )
  })

  it('文案含用户取消的错误也不记失败', () => {
    const { h, setRunError, pushItem } = handlers()
    handleForgeWsEvent(
      event(WSEventType.error, { code: 'SANDBOX_FAILED', message: '本轮生成失败：用户取消', fatal: true }),
      h,
    )
    expect(setRunError).not.toHaveBeenCalled()
    expect(pushItem).toHaveBeenCalledWith(
      expect.objectContaining({ label: 'runCancelled', tone: 'warn' }),
    )
  })

  it('用户已点取消后到达的失败事件不当作报错', () => {
    const { h, setRunError, pushItem } = handlers()
    h.isUserCancelled = () => true
    handleForgeWsEvent(
      event(WSEventType.error, { code: 'SANDBOX_FAILED', message: '沙箱失败', fatal: true }),
      h,
    )
    expect(setRunError).not.toHaveBeenCalled()
    expect(pushItem).toHaveBeenCalledWith(
      expect.objectContaining({ tone: 'warn' }),
    )
  })

  it('用户已点取消后失败的 tool_call 不记错误', () => {
    const { h, pushItem } = handlers()
    h.isUserCancelled = () => true
    handleForgeWsEvent(
      event(WSEventType.tool_call, { summary: 'aborted', status: 'error', phase: 'code' }),
      h,
    )
    expect(pushItem).not.toHaveBeenCalled()
  })

  it('phase_start 过程话进入 thinking，不进正文', () => {
    const { h } = handlers()
    handleForgeWsEvent(event(WSEventType.phase_start, { phase: RunPhase.art }), h)
    expect(h.appendMessages).toHaveBeenCalledWith(
      [expect.objectContaining({ kind: 'thinking', content: 'phaseArtStarted' })],
      'thinking',
    )
  })

  it('skill tool_call 在事件日志里标出 skill id', () => {
    const { h, pushItem } = handlers()
    handleForgeWsEvent(
      event(WSEventType.tool_call, {
        tool: 'skill',
        summary: 'art/ink-wash',
        status: 'ok',
        phase: RunPhase.art,
        args: { skill_ids: ['art/ink-wash'] },
      }),
      h,
    )
    expect(pushItem).toHaveBeenCalledWith(
      expect.objectContaining({
        label: 'skillCall',
        detail: 'art/ink-wash',
        tone: 'ok',
        phase: RunPhase.art,
      }),
    )
  })

  it('repair skill 记入开发列', () => {
    const { h, pushItem } = handlers()
    handleForgeWsEvent(
      event(WSEventType.tool_call, {
        tool: 'skill',
        summary: 'runtime-error',
        status: 'ok',
        phase: 'repair',
        args: { skill_ids: ['repair/runtime-error'], skill_names: ['Runtime'] },
      }),
      h,
    )
    expect(pushItem).toHaveBeenCalledWith(
      expect.objectContaining({ phase: RunPhase.code, detail: 'Runtime' }),
    )
  })

  it('hitl_wait 策划确认进 thinking，不进 design 正文', () => {
    const { h } = handlers()
    handleForgeWsEvent(
      event(WSEventType.hitl_wait, {
        node: 'plan_confirm',
        design_doc: { title: '霓虹躲避' },
        action_url: '/hitl',
      }),
      h,
    )
    expect(h.appendMessages).toHaveBeenCalledWith(
      [expect.objectContaining({ kind: 'thinking', content: expect.stringContaining('confirmDesign') })],
      'thinking',
    )
  })

  it('done 使用后端完成卡文案', () => {
    const { h } = handlers()
    handleForgeWsEvent(
      event(WSEventType.done, {
        game_id: 'game-1',
        version: 2,
        message: '# 任务执行已完成\n\n- WASD 移动',
      }),
      h,
    )
    expect(h.appendMessages).toHaveBeenCalledWith(
      [
        expect.objectContaining({
          kind: 'completed',
          content: '# 任务执行已完成\n\n- WASD 移动',
        }),
      ],
      'completed',
    )
  })

  it('真正的生成失败仍记入错误', () => {
    const { h, setRunStatus, setRunError, pushItem } = handlers()
    handleForgeWsEvent(
      event(WSEventType.error, { code: 'SANDBOX_FAILED', message: '沙箱失败', fatal: true }),
      h,
    )
    expect(setRunStatus).toHaveBeenCalledWith(RunStatus.failed)
    expect(setRunError).toHaveBeenCalledWith('run-1', '沙箱失败')
    expect(pushItem).toHaveBeenCalledWith(
      expect.objectContaining({ tone: 'err' }),
    )
  })
})
