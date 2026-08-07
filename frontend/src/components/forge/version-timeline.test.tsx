import { describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { VersionTimeline } from './VersionTimeline'
import type { GameVersion } from '@/api/types'

const versions: GameVersion[] = [
  { version: 2, artifact_path: '/a/2', created_at: '2026-08-07T10:00:00Z' },
  { version: 1, artifact_path: '/a/1', created_at: '2026-08-06T10:00:00Z' },
]

function renderTimeline(props: Partial<ComponentProps<typeof VersionTimeline>> = {}) {
  const onPreview = vi.fn()
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <VersionTimeline
        gameId="g-1"
        currentVersion={1}
        latestVersion={2}
        embeddedVersions={versions}
        accessToken="tok"
        previewVersion={1}
        onPreview={onPreview}
        {...props}
      />
    </QueryClientProvider>,
  )
  return { onPreview }
}

describe('VersionTimeline', () => {
  it('renders versions and calls onPreview without activate when previewing current', () => {
    const { onPreview } = renderTimeline()
    expect(screen.getAllByTestId('preview-v2').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /^设为当前版本$|^Set as current$/i })).toBeNull()
    fireEvent.click(screen.getAllByTestId('preview-v2')[0]!)
    expect(onPreview).toHaveBeenCalledWith(2)
  })

  it('shows set-current when preview differs from active version', () => {
    renderTimeline({ previewVersion: 2, currentVersion: 1 })
    expect(screen.getByRole('button', { name: /^设为当前版本$|^Set as current$/i })).toBeTruthy()
  })
})
