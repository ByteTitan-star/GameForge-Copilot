import { publicGamesApi, type PublicGame } from './public-games'

export type PlayMeta = {
  game_id?: string
  title: string
  author_display: string
  author_handle?: string | null
  published_at: string | null
  play_count: number
}

function toPlayMeta(game: PublicGame): PlayMeta {
  return {
    game_id: game.game_id,
    title: game.title,
    author_display: game.creator?.display_name ?? game.author_display ?? 'GameForge',
    author_handle: game.creator?.handle ?? game.author_handle ?? null,
    published_at: game.published_at ?? null,
    play_count: game.play_count,
  }
}

export const playApi = {
  /** Resolve play page metadata via GET /games/public/{slug}. */
  async getMeta(slug: string, locale?: string): Promise<PlayMeta> {
    const game = await publicGamesApi.getBySlug(slug, locale)
    return toPlayMeta(game)
  },
}
