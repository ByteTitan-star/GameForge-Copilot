import { apiRequest } from './client'

export type CreatorRef = {
  handle: string
  display_name?: string | null
}

export type PublicGame = {
  game_id: string
  title: string
  slug: string
  /** 生成时自动截图的真封面；无则回退官方静态 PNG → 渐变（见 PublicGameCard） */
  cover_url?: string | null
  play_count: number
  published_at?: string | null
  author_display?: string
  author_handle?: string | null
  creator?: CreatorRef | null
  featured?: boolean
}

export const publicGamesApi = {
  async list(locale?: string): Promise<PublicGame[]> {
    const q = locale ? `?locale=${encodeURIComponent(locale)}` : ''
    return apiRequest<PublicGame[]>(`/games/public${q}`)
  },

  async getBySlug(slug: string, locale?: string): Promise<PublicGame> {
    const q = locale ? `?locale=${encodeURIComponent(locale)}` : ''
    return apiRequest<PublicGame>(`/games/public/${encodeURIComponent(slug)}${q}`)
  },
}
