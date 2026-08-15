import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CustomColorField } from './CustomColorField'

vi.mock('@/i18n/use-t', () => ({
  useT: () => (key: string) => (key === 'themeInvalidColor' ? 'Invalid color' : key),
}))

afterEach(cleanup)

describe('CustomColorField', () => {
  it('shows validation error and keeps last valid color for invalid text', () => {
    const onCommit = vi.fn()
    render(
      <CustomColorField
        colorKey="primary"
        label="Primary"
        hint="Accent"
        value="#2563EB"
        onCommit={onCommit}
      />,
    )

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '#GGGGGG' } })
    fireEvent.blur(input)

    expect(screen.getByRole('alert')).toHaveTextContent('Invalid color')
    expect(onCommit).not.toHaveBeenCalled()
    expect(input).toHaveValue('#2563EB')
  })

  it('commits normalized hex on blur', () => {
    const onCommit = vi.fn()
    render(
      <CustomColorField
        colorKey="primary"
        label="Primary"
        hint="Accent"
        value="#2563EB"
        onCommit={onCommit}
      />,
    )

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '#abc' } })
    fireEvent.blur(input)

    expect(onCommit).toHaveBeenCalledWith('primary', '#AABBCC')
  })
})
