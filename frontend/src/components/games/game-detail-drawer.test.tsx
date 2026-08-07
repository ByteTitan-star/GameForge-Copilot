import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { GameDetailDrawer } from './GameDetailDrawer'
import type { GameSummary } from '@/api/types'
import { GameStatus } from '@/api/enums'

vi.mock('@/api/games', () => ({
  gamesApi: {
    get: vi.fn().mockResolvedValue({
      game_id: 'g-1',
      title: 'Test game',
      current_version: 2,
      versions: [{ version: 2, artifact_path: '/a', created_at: '2026-08-07T10:00:00Z' }],
    }),
  },
}))

const game: GameSummary = {
  game_id: 'g-1',
  title: 'Test game',
  status: GameStatus.draft,
  current_version: 2,
  slug: null,
  updated_at: '2026-08-07T10:00:00Z',
}

describe('GameDetailDrawer', () => {
  it('opens with version history when game has builds', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <MemoryRouter>
        <QueryClientProvider client={qc}>
          <GameDetailDrawer game={game} accessToken="tok" onClose={() => {}} />
        </QueryClientProvider>
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: 'Test game' })).toBeTruthy()
    await waitFor(() => {
      expect(screen.getAllByTestId('preview-v2').length).toBeGreaterThan(0)
    })
  })
})
