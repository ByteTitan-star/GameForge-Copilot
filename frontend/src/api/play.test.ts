import { afterEach, describe, expect, it, vi } from 'vitest'
import { playApi } from './play'

describe('playApi.getMeta', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads metadata from GET /games/public/{slug} without list fallback', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            game_id: '00000000-0000-4000-8000-0000000000a1',
            title: 'Neon Snake',
            slug: 'official-neon-snake',
            play_count: 42,
            published_at: '2026-01-01T00:00:00Z',
            creator: { handle: 'official', display_name: 'GameForge Official' },
          },
        }),
        { headers: { 'Content-Type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const meta = await playApi.getMeta('official-neon-snake')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toMatch(/\/games\/public\/official-neon-snake$/)
    expect(meta.title).toBe('Neon Snake')
    expect(meta.game_id).toBe('00000000-0000-4000-8000-0000000000a1')
    expect(meta.author_handle).toBe('official')
    expect(meta.play_count).toBe(42)
  })
})
