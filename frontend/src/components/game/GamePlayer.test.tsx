import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useLocaleStore } from '@/stores/locale-store'
import { GamePlayer } from './GamePlayer'

describe('GamePlayer', () => {
  beforeEach(() => {
    useLocaleStore.setState({ locale: 'zh' })
  })

  it('removes the loading overlay after the iframe finishes loading', async () => {
    render(<GamePlayer src="https://example.test/game" title="Test game" />)

    fireEvent.load(screen.getByTitle('Test game'))

    await waitFor(() => {
      expect(screen.queryByText('加载中…')).not.toBeInTheDocument()
    })
  })
})
