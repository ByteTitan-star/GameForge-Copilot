import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { GamePlayer } from './GamePlayer'

describe('GamePlayer draft authentication', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('鉴权 fetch 完成前不把 draft URL 直接挂到 iframe', async () => {
    let resolveFetch!: (response: Response) => void
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve
    })
    const fetchMock = vi.fn(() => fetchPromise)
    vi.stubGlobal('fetch', fetchMock)
    render(
      <GamePlayer
        src="http://127.0.0.1:8000/draft/game-1/1"
        accessToken="token-1"
        variant="stage"
      />,
    )

    expect(screen.queryByTitle('Game preview')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/draft\/game-1\/1(?:\?v=\d+)?$/),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer token-1' }),
      }),
    )

    resolveFetch(new Response('<!doctype html><title>game</title>', { status: 200 }))
    await waitFor(() =>
      expect(screen.getByTitle('Game preview')).toHaveAttribute(
        'srcdoc',
        '<!doctype html><title>game</title>',
      ),
    )
    fireEvent.load(screen.getByTitle('Game preview'))
    await waitFor(() => expect(screen.queryByText('加载中…')).not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
