import { describe, expect, it } from 'vitest'
import { pickDefaultLlmConfigId } from '@/lib/llm-config'
import type { LlmConfig } from '@/api/types'

describe('pickDefaultLlmConfigId', () => {
  it('returns default config when marked', () => {
    const configs = [
      { config_id: 'a', is_default: false },
      { config_id: 'b', is_default: true },
    ] as LlmConfig[]
    expect(pickDefaultLlmConfigId(configs)).toBe('b')
  })

  it('falls back to first config', () => {
    const configs = [{ config_id: 'only', is_default: false }] as LlmConfig[]
    expect(pickDefaultLlmConfigId(configs)).toBe('only')
  })

  it('returns null when empty', () => {
    expect(pickDefaultLlmConfigId([])).toBeNull()
  })
})
