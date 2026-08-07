import { env } from '@/lib/env'
import { publicGamesApi } from './public-games'

export type PlayMeta = {
  game_id?: string
  title: string
  author_display: string
  author_handle?: string | null
  published_at: string | null
  play_count: number
}

async function tryFetchMeta(slug: string): Promise<PlayMeta | null> {
  const res = await fetch(`${env.apiBaseUrl}/play/${encodeURIComponent(slug)}/meta`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) return null
  const json = (await res.json()) as { data?: PlayMeta }
  if (!json.data?.title) return null
  return json.data
}

export const playApi = {
  /** meta 端点未就绪时从公开列表或 slug 回退 */
  async getMeta(slug: string): Promise<PlayMeta> {
    try {
      const live = await tryFetchMeta(slug)
      if (live) return live
    } catch {
      /* fallback */
    }
    try {
      const pub = await publicGamesApi.list()
      const match = pub.find((g) => g.slug === slug)
      if (match) {
        return {
          game_id: match.game_id,
          title: match.title,
          author_display: match.author_display ?? 'GameForge',
          author_handle: match.author_handle ?? match.creator?.handle ?? null,
          published_at: match.published_at,
          play_count: match.play_count,
        }
      }
    } catch {
      /* fallback */
    }
    return {
      title: slug,
      author_display: '',
      published_at: null,
      play_count: 0,
    }
  },
}
