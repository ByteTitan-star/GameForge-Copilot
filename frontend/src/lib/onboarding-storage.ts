export const ONBOARDING_DONE_KEY = 'onboarding_v1_done'

export function isOnboardingDone(): boolean {
  if (typeof window === 'undefined') return true
  return window.localStorage.getItem(ONBOARDING_DONE_KEY) === '1'
}

export function markOnboardingDone(): void {
  window.localStorage.setItem(ONBOARDING_DONE_KEY, '1')
}
