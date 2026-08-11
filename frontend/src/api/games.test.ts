import { afterEach, describe, expect, it, vi } from 'vitest'
import { gamesApi } from './games'

describe('gamesApi.downloadVersion', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses Bearer authentication and returns the downloaded HTML blob', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('<!doctype html><title>Game</title>', {
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Content-Disposition': "attachment; filename*=UTF-8''game-v2.html",
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const file = await gamesApi.downloadVersion('game-1', 2, 'token-1')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/games\/game-1\/versions\/2\/download$/),
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: 'text/html',
          Authorization: 'Bearer token-1',
        }),
      }),
    )
    expect(file.filename).toBe('game-v2.html')
    expect(await file.blob.text()).toContain('<title>Game</title>')
  })
})
