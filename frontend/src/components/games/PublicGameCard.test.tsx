import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { PublicGameCard } from './PublicGameCard'

describe('PublicGameCard', () => {
  it('omits timestamp when published_at is absent', () => {
    render(
      <MemoryRouter>
        <PublicGameCard
          game={{
            game_id: '00000000-0000-4000-8000-0000000000a3',
            title: 'Tower Stub',
            slug: 'official-tower-stub',
            play_count: 12,
          }}
          variant="theme"
          showFeaturedBadge={false}
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Tower Stub' })).toBeTruthy()
    expect(screen.queryByText(/Invalid Date/i)).toBeNull()
  })

  it('links play action to public slug route', () => {
    render(
      <MemoryRouter>
        <PublicGameCard
          game={{
            game_id: 'g1',
            title: 'Neon Snake',
            slug: 'official-neon-snake',
            play_count: 3,
            published_at: '2026-01-01T00:00:00Z',
          }}
          variant="theme"
          showFeaturedBadge={false}
        />
      </MemoryRouter>,
    )
    const links = screen.getAllByRole('link')
    expect(links.some((a) => a.getAttribute('href') === '/play/official-neon-snake')).toBe(true)
  })
})
