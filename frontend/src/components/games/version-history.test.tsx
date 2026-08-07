import { describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { VersionHistoryPanel } from './VersionHistoryPanel'
import type { GameVersion } from '@/api/types'

const versions: GameVersion[] = [
  { version: 2, artifact_path: '/a/2', created_at: '2026-08-07T10:00:00Z' },
  { version: 1, artifact_path: '/a/1', created_at: '2026-08-06T10:00:00Z' },
]

function renderPanel(props: Partial<ComponentProps<typeof VersionHistoryPanel>> = {}) {
  const onPreview = vi.fn()
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <VersionHistoryPanel
        gameId="g-1"
        currentVersion={2}
        embeddedVersions={versions}
        accessToken="tok"
        previewVersion={2}
        onPreview={onPreview}
        {...props}
      />
    </QueryClientProvider>,
  )
  return { onPreview }
}

describe('VersionHistoryPanel', () => {
  it('渲染版本列表并标记当前版本', () => {
    renderPanel()
    expect(screen.getAllByTestId('preview-v2').length).toBeGreaterThan(0)
    expect(screen.getAllByTestId('preview-v1').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/当前|Current/).length).toBeGreaterThan(0)
  })
})
