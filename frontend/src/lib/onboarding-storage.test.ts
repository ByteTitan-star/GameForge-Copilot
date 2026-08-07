import { afterEach, describe, expect, it } from 'vitest'
import {
  isOnboardingDone,
  markOnboardingDone,
  ONBOARDING_DONE_KEY,
} from './onboarding-storage'

describe('onboarding-storage', () => {
  afterEach(() => {
    window.localStorage.removeItem(ONBOARDING_DONE_KEY)
  })

  it('starts incomplete then marks done', () => {
    expect(isOnboardingDone()).toBe(false)
    markOnboardingDone()
    expect(isOnboardingDone()).toBe(true)
  })
})
