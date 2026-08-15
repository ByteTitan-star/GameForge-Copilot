import { apiRequest } from './client'
import type { PublicGame } from './public-games'

export const featuredApi = {
  async list(locale?: string): Promise<PublicGame[]> {
    const q = locale ? `?locale=${encodeURIComponent(locale)}` : ''
    return apiRequest<PublicGame[]>(`/games/featured${q}`)
  },
}
