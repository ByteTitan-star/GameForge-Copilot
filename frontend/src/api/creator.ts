import { env } from '@/lib/env'

export type CreatorGame = {
  game_id: string
  title: string
  slug: string
  play_count: number
  published_at: string
}

export type CreatorProfile = {
  handle: string
  display_name: string
  total_plays: number
  latest_published_at: string | null
  games: CreatorGame[]
}

async function tryFetch(handle: string): Promise<CreatorProfile | null> {
  const res = await fetch(`${env.apiBaseUrl}/u/${encodeURIComponent(handle)}`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) return null
  const json = (await res.json()) as { data?: CreatorProfile }
  if (!json.data?.handle) return null
  return json.data
}

export const creatorApi = {
  /** B-C2 未就绪时返回 null，页面展示 404 */
  async get(handle: string): Promise<CreatorProfile | null> {
    try {
      return await tryFetch(handle)
    } catch {
      return null
    }
  },
}
