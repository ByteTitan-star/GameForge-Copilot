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
  /** 通过契约端点 GET /games/public/{slug} 解析试玩页元数据（不再请求未实现的 /play/{slug}/meta）。 */
  async getMeta(slug: string): Promise<PlayMeta> {
    try {
      const game = await publicGamesApi.getBySlug(slug)
      return toPlayMeta(game)
    } catch {
      return {
        title: slug,
        author_display: '',
        published_at: null,
        play_count: 0,
      }
    }
  },
}
