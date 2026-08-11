import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { VersionHistoryPanel } from './VersionHistoryPanel'
import type { GameVersion } from '@/api/types'
import { gamesApi } from '@/api/games'
import { downloadFile } from '@/lib/download-file'

vi.mock('@/api/games', () => ({
  gamesApi: { downloadVersion: vi.fn() },
}))

vi.mock('@/lib/download-file', () => ({ downloadFile: vi.fn() }))

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
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('渲染版本列表并标记当前版本', () => {
    renderPanel()
    expect(screen.getAllByTestId('preview-v2').length).toBeGreaterThan(0)
    expect(screen.getAllByTestId('preview-v1').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/当前|Current/).length).toBeGreaterThan(0)
  })

  it('downloads both the current and a historical version', async () => {
    const blob = new Blob(['<!doctype html>'], { type: 'text/html' })
    vi.mocked(gamesApi.downloadVersion).mockResolvedValue({ blob, filename: 'game-v2.html' })
    renderPanel()

    fireEvent.click(screen.getByTestId('download-v2'))
    await waitFor(() => {
      expect(gamesApi.downloadVersion).toHaveBeenCalledWith('g-1', 2, 'tok')
    })
    expect(downloadFile).toHaveBeenLastCalledWith(blob, 'game-v2.html')

    fireEvent.click(screen.getByTestId('download-v1'))
    await waitFor(() => {
      expect(gamesApi.downloadVersion).toHaveBeenLastCalledWith('g-1', 1, 'tok')
    })
  })

  it('shows a pending state while the version file is downloading', async () => {
    let resolveDownload!: (file: { blob: Blob; filename: string | null }) => void
    vi.mocked(gamesApi.downloadVersion).mockReturnValue(
      new Promise((resolve) => {
        resolveDownload = resolve
      }),
    )
    renderPanel()

    fireEvent.click(screen.getByTestId('download-v1'))

    const button = screen.getByTestId('download-v1')
    expect(button).toBeDisabled()
    expect(button.getAttribute('aria-label')).toMatch(/正在下载|Downloading/)

    resolveDownload({ blob: new Blob(['ok']), filename: 'game-v1.html' })
    await waitFor(() => expect(button).toBeEnabled())
  })

  it('shows a failure message and restores the button after a failed download', async () => {
    vi.mocked(gamesApi.downloadVersion).mockRejectedValue(new Error('network failed'))
    renderPanel()

    fireEvent.click(screen.getByTestId('download-v1'))

    expect(await screen.findByRole('alert')).toHaveTextContent('network failed')
    expect(screen.getByTestId('download-v1')).toBeEnabled()
  })
})
