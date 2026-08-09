import { apiRequest } from './client'

/** 公开广场条目（契约 B2） */
export type CreatorRef = {
  handle: string
  display_name?: string | null
}

export type PublicGame = {
  game_id: string
  title: string
  slug: string
  play_count: number
  published_at: string
  author_display?: string
  author_handle?: string | null
  creator?: CreatorRef | null
  featured?: boolean
}

export const publicGamesApi = {
  async list(): Promise<PublicGame[]> {
    return apiRequest<PublicGame[]>('/games/public')
  },
}
