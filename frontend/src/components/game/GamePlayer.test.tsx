import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const mintDraftPreviewUrl = vi.fn()
const fetchDraftHtml = vi.fn()

vi.mock('@/lib/hosting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/hosting')>()
  return {
    ...actual,
    mintDraftPreviewUrl: (...args: unknown[]) => mintDraftPreviewUrl(...args),
    fetchDraftHtml: (...args: unknown[]) => fetchDraftHtml(...args),
  }
})

import { GamePlayer } from './GamePlayer'

describe('GamePlayer draft authentication', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    mintDraftPreviewUrl.mockReset()
    fetchDraftHtml.mockReset()
  })

  it('草稿 URL 兑换 preview token 后挂 iframe src，不用 srcDoc', async () => {
    mintDraftPreviewUrl.mockResolvedValue('http://127.0.0.1:8000/preview/tok/game-1/1/')
    render(
      <GamePlayer
        src="http://127.0.0.1:8000/draft/game-1/1"
        accessToken="token-1"
        variant="stage"
      />,
    )

    expect(screen.queryByTitle('Game preview')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByTitle('Game preview')).toHaveAttribute(
        'src',
        'http://127.0.0.1:8000/preview/tok/game-1/1/',
      ),
    )
    expect(screen.getByTitle('Game preview')).not.toHaveAttribute('srcdoc')
    expect(mintDraftPreviewUrl).toHaveBeenCalledWith('game-1', '1', 'token-1')
    expect(fetchDraftHtml).not.toHaveBeenCalled()
    fireEvent.load(screen.getByTitle('Game preview'))
    await waitFor(() => expect(screen.queryByText('加载中…')).not.toBeInTheDocument())
  })

  it('preview token 兑换失败时显示错误，不回退 srcDoc', async () => {
    mintDraftPreviewUrl.mockRejectedValue(new Error('token mint failed'))
    render(
      <GamePlayer
        src="http://127.0.0.1:8000/draft/game-1/1"
        accessToken="token-1"
        variant="stage"
      />,
    )
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText('加载失败')).toBeInTheDocument()
    expect(screen.getByText('token mint failed')).toBeInTheDocument()
    expect(screen.queryByTitle('Game preview')).not.toBeInTheDocument()
    expect(fetchDraftHtml).not.toHaveBeenCalled()
  })

  it('preview token URL 直接挂 iframe，不走兑换', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(
      <GamePlayer
        src="http://127.0.0.1:8000/preview/tok/game-1/1/"
        accessToken="token-1"
        variant="stage"
      />,
    )
    await waitFor(() =>
      expect(screen.getByTitle('Game preview')).toHaveAttribute(
        'src',
        'http://127.0.0.1:8000/preview/tok/game-1/1/',
      ),
    )
    expect(mintDraftPreviewUrl).not.toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
