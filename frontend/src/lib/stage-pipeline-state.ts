import { RunPhase } from '@/api/enums'
import { PIPELINE_PHASES } from '@/lib/phase-labels'

export type StageStatus = 'pending' | 'active' | 'done' | 'failed'

export type StageInfo = {
  status: StageStatus
  humanLabel?: string
  etaSeconds?: number
}

export type StagePipelineState = Record<RunPhase, StageInfo>

export function emptyStagePipeline(): StagePipelineState {
  return {
    [RunPhase.plan]: { status: 'pending' },
    [RunPhase.art]: { status: 'pending' },
    [RunPhase.code]: { status: 'pending' },
    [RunPhase.qa]: { status: 'pending' },
    [RunPhase.done]: { status: 'pending' },
  }
}

export function applyPhaseStart(
  state: StagePipelineState,
  phase: RunPhase,
  humanLabel?: string,
  etaSeconds?: number,
): StagePipelineState {
  const next = { ...state }
  for (const p of PIPELINE_PHASES) {
    const idx = PIPELINE_PHASES.indexOf(p)
    const targetIdx = PIPELINE_PHASES.indexOf(phase)
    if (idx < targetIdx) next[p] = { ...next[p], status: 'done' }
    else if (p === phase) {
      next[p] = {
        status: 'active',
        humanLabel: humanLabel ?? next[p].humanLabel,
        etaSeconds: etaSeconds ?? next[p].etaSeconds,
      }
    } else if (idx > targetIdx) {
      next[p] = { ...next[p], status: 'pending' }
    }
  }
  return next
}

export function markStageFailed(state: StagePipelineState, phase: RunPhase): StagePipelineState {
  return {
    ...state,
    [phase]: { ...state[phase], status: 'failed' },
  }
}

export function markAllDone(state: StagePipelineState): StagePipelineState {
  const next = { ...state }
  for (const p of PIPELINE_PHASES) {
    next[p] = { ...next[p], status: 'done' }
  }
  return next
}
