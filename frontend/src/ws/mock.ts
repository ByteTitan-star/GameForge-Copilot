import { RunPhase, WSEventType } from '@/api/enums'
import type { WsEnvelope } from '@/api/types.gen'

type Step = { delayMs: number; event: Omit<WsEnvelope, 'run_id' | 'ts'> }

/** 按时间线回放一次完整生成（含 HITL 暂停点） */
export function buildMockRunTimeline(runId: string, gameId: string, title: string): Step[] {
  const base = (type: WsEnvelope['type'], payload: Record<string, unknown>): Step['event'] => ({
    type,
    payload,
  })

  return [
    { delayMs: 400, event: base(WSEventType.phase_start, { phase: RunPhase.plan }) },
    {
      delayMs: 900,
      event: base(WSEventType.llm_call, {
        phase: RunPhase.plan,
        model: 'claude-sonnet-4-20250514',
        provider: 'anthropic',
        input_tokens: 1200,
        output_tokens: 480,
      }),
    },
    {
      delayMs: 700,
      event: base(WSEventType.hitl_wait, {
        node: 'plan_confirm',
        design_doc: {
          title,
          gameplay: '核心循环：移动、收集、计分；失败后一键重开。',
          controls: '方向键 / WASD；空格暂停。',
          levels: ['热身关', '加速关', '障碍关'],
        },
        action_url: `/api/v1/games/${gameId}/runs/${runId}/hitl/resolve`,
      }),
    },
  ]
}

export function buildMockRunAfterHitl(runId: string, gameId: string): Step[] {
  const base = (type: WsEnvelope['type'], payload: Record<string, unknown>): Step['event'] => ({
    type,
    payload,
  })

  return [
    { delayMs: 500, event: base(WSEventType.phase_start, { phase: RunPhase.art }) },
    {
      delayMs: 800,
      event: base(WSEventType.tool_call, {
        phase: RunPhase.art,
        tool: 'generate_sprites',
        status: 'ok',
        summary: '生成角色与障碍素材包',
      }),
    },
    { delayMs: 600, event: base(WSEventType.phase_start, { phase: RunPhase.code }) },
    {
      delayMs: 1000,
      event: base(WSEventType.llm_call, {
        phase: RunPhase.code,
        model: 'claude-sonnet-4-20250514',
        provider: 'anthropic',
        input_tokens: 3400,
        output_tokens: 2100,
      }),
    },
    {
      delayMs: 900,
      event: base(WSEventType.tool_call, {
        phase: RunPhase.code,
        tool: 'execute_code',
        status: 'ok',
        summary: '沙箱构建成功',
      }),
    },
    {
      delayMs: 500,
      event: base(WSEventType.build_done, {
        version: 1,
        artifact_path: `/mock-artifacts/${gameId}/v1/`,
        preview_url: `/draft/${gameId}/1`,
      }),
    },
    { delayMs: 700, event: base(WSEventType.phase_start, { phase: RunPhase.qa }) },
    {
      delayMs: 800,
      event: base(WSEventType.qa_report, {
        passed: true,
        issues: ['启动正常', '计分递增正常', '移动边界 OK'],
        log_excerpt: 'QA suite: 12/12 passed',
      }),
    },
    { delayMs: 500, event: base(WSEventType.phase_start, { phase: RunPhase.done }) },
    {
      delayMs: 400,
      event: base(WSEventType.done, {
        run_id: runId,
        game_id: gameId,
        version: 1,
        preview_url: `/draft/${gameId}/1`,
      }),
    },
  ]
}

export type MockRunHandle = { cancel: () => void }

export function playMockTimeline(
  steps: Step[],
  runId: string,
  onEvent: (ev: WsEnvelope) => void,
): MockRunHandle {
  let cancelled = false
  const timers: number[] = []
  let acc = 0
  for (const step of steps) {
    acc += step.delayMs
    const t = window.setTimeout(() => {
      if (cancelled) return
      onEvent({
        type: step.event.type,
        run_id: runId,
        ts: new Date().toISOString(),
        payload: step.event.payload,
      })
    }, acc)
    timers.push(t)
  }
  return {
    cancel: () => {
      cancelled = true
      timers.forEach((id) => window.clearTimeout(id))
    },
  }
}
