import { env } from '@/lib/env'
import type { PublicGame } from './public-games'
import { MOCK_PUBLIC_GAMES } from './public-games'

async function tryFetch(): Promise<PublicGame[] | null> {
  const res = await fetch(`${env.apiBaseUrl}/games/featured`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) return null
  const json = (await res.json()) as { data?: PublicGame[] }
  if (!json.data?.length) return null
  return json.data
}

export const featuredApi = {
  async list(): Promise<PublicGame[]> {
    try {
      const live = await tryFetch()
      if (live?.length) return live
    } catch {
      /* fallback */
    }
    return MOCK_PUBLIC_GAMES.slice(0, 2)
  },
}
