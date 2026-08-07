import { describe, expect, it } from 'vitest'
import { RunPhase } from '@/api/enums'
import {
  applyPhaseStart,
  emptyStagePipeline,
  markAllDone,
  markStageFailed,
} from './stage-pipeline-state'

describe('stage-pipeline-state', () => {
  it('applyPhaseStart marks earlier phases done and target active', () => {
    let state = emptyStagePipeline()
    state = applyPhaseStart(state, RunPhase.plan, 'Planning', 90)
    expect(state.plan.status).toBe('active')
    expect(state.plan.humanLabel).toBe('Planning')
    expect(state.art.status).toBe('pending')

    state = applyPhaseStart(state, RunPhase.code, 'Building', 120)
    expect(state.plan.status).toBe('done')
    expect(state.art.status).toBe('done')
    expect(state.code.status).toBe('active')
    expect(state.qa.status).toBe('pending')
  })

  it('markStageFailed and markAllDone', () => {
    let state = applyPhaseStart(emptyStagePipeline(), RunPhase.qa)
    state = markStageFailed(state, RunPhase.qa)
    expect(state.qa.status).toBe('failed')

    state = markAllDone(state)
    expect(state.plan.status).toBe('done')
    expect(state.qa.status).toBe('done')
  })
})
