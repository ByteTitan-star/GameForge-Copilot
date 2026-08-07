import { apiRequest } from './client'
import type { PublicGame } from './public-games'

export type ReactionState = {
  liked: boolean
  favorited: boolean
  like_count: number
}

const localLikes = new Set<string>()
const localFavorites = new Set<string>()

export const reactionsApi = {
  async getState(gameId: string, accessToken?: string | null): Promise<ReactionState> {
    if (!accessToken) {
      return {
        liked: localLikes.has(gameId),
        favorited: localFavorites.has(gameId),
        like_count: localLikes.has(gameId) ? 1 : 0,
      }
    }
    try {
      return await apiRequest<ReactionState>(`/games/${gameId}/reactions`, {
        token: accessToken,
      })
    } catch {
      return {
        liked: localLikes.has(gameId),
        favorited: localFavorites.has(gameId),
        like_count: 0,
      }
    }
  },

  async toggleLike(gameId: string, liked: boolean, accessToken: string) {
    try {
      if (liked) {
        await apiRequest<void>(`/games/${gameId}/like`, {
          method: 'DELETE',
          token: accessToken,
        })
        localLikes.delete(gameId)
      } else {
        await apiRequest<void>(`/games/${gameId}/like`, {
          method: 'POST',
          token: accessToken,
          body: {},
        })
        localLikes.add(gameId)
      }
    } catch {
      if (liked) localLikes.delete(gameId)
      else localLikes.add(gameId)
    }
  },

  async toggleFavorite(gameId: string, favorited: boolean, accessToken: string) {
    try {
      if (favorited) {
        await apiRequest<void>(`/games/${gameId}/favorite`, {
          method: 'DELETE',
          token: accessToken,
        })
        localFavorites.delete(gameId)
      } else {
        await apiRequest<void>(`/games/${gameId}/favorite`, {
          method: 'POST',
          token: accessToken,
          body: {},
        })
        localFavorites.add(gameId)
      }
    } catch {
      if (favorited) localFavorites.delete(gameId)
      else localFavorites.add(gameId)
    }
  },

  async listFavorites(accessToken: string): Promise<PublicGame[]> {
    try {
      const rows = await apiRequest<PublicGame[]>('/me/favorites', { token: accessToken })
      return rows ?? []
    } catch {
      return []
    }
  },
}
