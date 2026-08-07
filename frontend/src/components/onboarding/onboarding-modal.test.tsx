import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { OnboardingModal } from './OnboardingModal'
import { ONBOARDING_DONE_KEY } from '@/lib/onboarding-storage'

function renderModal(open = true) {
  const onClose = vi.fn()
  render(
    <MemoryRouter>
      <OnboardingModal open={open} onClose={onClose} />
    </MemoryRouter>,
  )
  return { onClose }
}

describe('OnboardingModal', () => {
  it('skip marks onboarding done and closes', () => {
    window.localStorage.removeItem(ONBOARDING_DONE_KEY)
    const { onClose } = renderModal()
    fireEvent.click(screen.getByText(/跳过|Skip/i))
    expect(window.localStorage.getItem(ONBOARDING_DONE_KEY)).toBe('1')
    expect(onClose).toHaveBeenCalled()
  })
})
