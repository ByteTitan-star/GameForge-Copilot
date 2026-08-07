import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SharePosterModal } from './SharePosterModal'

describe('SharePosterModal', () => {
  it('renders and closes', () => {
    const onClose = vi.fn()
    render(
      <SharePosterModal open title="Neon Snake" slug="neon-snake" onClose={onClose} />,
    )
    expect(screen.getByText(/分享海报|Share poster/i)).toBeTruthy()
    fireEvent.click(screen.getByLabelText(/关闭|Close/i))
    expect(onClose).toHaveBeenCalled()
  })
})
