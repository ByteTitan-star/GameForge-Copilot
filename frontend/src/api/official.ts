import { apiRequest } from './client'
import type { CreateGameResponse } from './types'

export type OfficialGame = {
  slug: string
  title: string
  description: string
  play_url: string
  thumbnail_url: string | null
}

export const officialApi = {
  /** GET /official-games */
  async list(locale?: string): Promise<OfficialGame[]> {
    const q = locale ? `?locale=${encodeURIComponent(locale)}` : ''
    return apiRequest<OfficialGame[]>(`/official-games${q}`)
  },

  /** POST /games/fork/{slug} — 404 时抛错由 UI toast */
  fork(slug: string, accessToken: string) {
    return apiRequest<CreateGameResponse>(`/games/fork/${encodeURIComponent(slug)}`, {
      method: 'POST',
      token: accessToken,
      body: {},
    })
  },
}
