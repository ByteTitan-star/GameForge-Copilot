import { apiRequest } from './client'
import type { PublicGame } from './public-games'

export const featuredApi = {
  async list(): Promise<PublicGame[]> {
    return apiRequest<PublicGame[]>('/games/featured')
  },
}
