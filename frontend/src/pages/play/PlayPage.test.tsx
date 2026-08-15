import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PlayPage } from './PlayPage'

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector: (s: { access_token: string | null; user: null }) => unknown) =>
    selector({ access_token: null, user: null }),
}))

vi.mock('@/api/play', () => ({
  playApi: {
    getMeta: vi.fn(),
  },
}))

vi.mock('@/components/game/GamePlayer', () => ({
  GamePlayer: () => <div data-testid="game-player" />,
}))

import { playApi } from '@/api/play'
import { ApiError } from '@/api/errors'

function renderPlay(slug: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/play/${slug}`]}>
        <Routes>
          <Route path="/play/:slug" element={<PlayPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PlayPage', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('未知 slug 显示 not-found 状态且不挂载 GamePlayer', async () => {
    vi.mocked(playApi.getMeta).mockRejectedValue(
      new ApiError(404, { code: 'GAME_NOT_FOUND', message: '游戏不存在或未发布' }),
    )

    renderPlay('does-not-exist')

    await waitFor(() =>
      expect(screen.getByText('游戏不存在或未发布')).toBeInTheDocument(),
    )
    expect(screen.queryByTestId('game-player')).not.toBeInTheDocument()
  })

  it('有效 slug 正常渲染试玩区', async () => {
    vi.mocked(playApi.getMeta).mockResolvedValue({
      game_id: 'game-1',
      title: 'Demo Game',
      author_display: 'Creator',
      published_at: '2026-01-01T00:00:00Z',
      play_count: 12,
    })

    renderPlay('demo-game')

    await waitFor(() => expect(screen.getByText('Demo Game')).toBeInTheDocument())
    expect(screen.getByTestId('game-player')).toBeInTheDocument()
  })
})
