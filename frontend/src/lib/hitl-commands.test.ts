import { describe, expect, it } from 'vitest'
import {
  commandForHitlAction,
  hitlAllows,
  nextPhaseAfterHitl,
} from './hitl-commands'

describe('hitl command helpers', () => {
  it('无 allowed_commands 时仍允许旧工作流操作', () => {
    expect(hitlAllows({ node: 'qa_failed' }, 'revise_plan')).toBe(true)
    expect(hitlAllows({ node: 'plan_confirm' }, 'cancel_run')).toBe(true)
  })

  it('legacy decision 映射为 command', () => {
    expect(commandForHitlAction('plan_confirm', 'approve')).toBe('approve_plan')
    expect(commandForHitlAction('art_confirm', 'select_a')).toBe('select_art_a')
    expect(commandForHitlAction('qa_failed', 'approve')).toBe('retry_implementation')
    expect(commandForHitlAction('qa_failed', 'modify', 'revise_plan')).toBe('revise_plan')
  })

  it('sandbox 默认包含 retry_infra', () => {
    expect(hitlAllows({ node: 'sandbox_failed' }, 'retry_infra')).toBe(true)
    expect(commandForHitlAction('sandbox_failed', 'approve')).toBe('retry_infra')
  })

  it('REVISE_PLAN 下一阶段回到策划', () => {
    expect(nextPhaseAfterHitl('qa_failed', 'revise_plan')).toBe('plan')
    expect(nextPhaseAfterHitl('art_confirm', 'revise_plan')).toBe('plan')
    expect(nextPhaseAfterHitl('plan_confirm', 'approve_plan')).toBe('art')
    expect(nextPhaseAfterHitl('qa_failed', 'retry_implementation')).toBe('code')
  })
})
