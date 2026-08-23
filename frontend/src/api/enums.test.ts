import { describe, expect, it } from 'vitest'
import {
  ErrorCode,
  GameStatus,
  LLMProvider,
  PublishStatus,
  Role,
  RunPhase,
  RunStatus,
  WSEventType,
} from './enums'

describe('enums 与 docs/10 §2 字面量一致', () => {
  it('Role', () => {
    expect(Object.values(Role).sort()).toEqual(['admin', 'user'])
  })

  it('GameStatus', () => {
    expect(Object.values(GameStatus).sort()).toEqual(
      ['draft', 'published', 'rejected', 'reviewing', 'submitted', 'taken_down'].sort(),
    )
  })

  it('RunStatus / RunPhase', () => {
    expect(Object.values(RunStatus).sort()).toEqual(
      ['cancelled', 'done', 'failed', 'paused', 'running'],
    )
    expect(Object.values(RunPhase).sort()).toEqual(['art', 'code', 'done', 'plan', 'qa'])
  })

  it('PublishStatus / LLMProvider / WSEventType / ErrorCode 核心码', () => {
    expect(Object.values(PublishStatus)).toContain('approved')
    expect(Object.values(LLMProvider)).toEqual(['anthropic', 'openai', 'openai_compat'])
    expect(Object.values(WSEventType)).toContain('hitl_wait')
    expect(ErrorCode.EMAIL_NOT_VERIFIED).toBe('EMAIL_NOT_VERIFIED')
    expect(ErrorCode.QUOTA_EXCEEDED).toBe('QUOTA_EXCEEDED')
  })
})
