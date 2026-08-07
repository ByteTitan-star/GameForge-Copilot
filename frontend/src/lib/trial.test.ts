import { describe, expect, it } from 'vitest'
import { TRIAL_EMAIL, isTrialEmail, isTrialUser } from './trial'

describe('trial account helpers', () => {
  it('recognizes trial email case-insensitively', () => {
    expect(isTrialEmail(TRIAL_EMAIL)).toBe(true)
    expect(isTrialEmail('Demo@GameForge.dev')).toBe(true)
    expect(isTrialEmail(' admin@gameforge.dev ')).toBe(false)
    expect(isTrialEmail(null)).toBe(false)
  })

  it('recognizes trial user by email', () => {
    expect(isTrialUser({ email: TRIAL_EMAIL })).toBe(true)
    expect(isTrialUser({ email: 'other@x.com' })).toBe(false)
    expect(isTrialUser(null)).toBe(false)
  })
})
