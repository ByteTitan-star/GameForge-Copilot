import { env } from '@/lib/env'

/** 公开广场条目（契约 B2；后端未就绪时走 Mock） */
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

const MOCK_PUBLIC_GAMES: PublicGame[] = [
  {
    game_id: '00000000-0000-4000-8000-000000000001',
    title: '霓虹贪吃蛇',
    slug: 'neon-snake',
    play_count: 1284,
    published_at: '2026-07-01T08:00:00Z',
    author_display: 'GameForge',
  },
  {
    game_id: '00000000-0000-4000-8000-000000000002',
    title: '双人像素闯关',
    slug: 'coop-pixel-run',
    play_count: 892,
    published_at: '2026-07-10T12:00:00Z',
    author_display: 'GameForge',
  },
  {
    game_id: '00000000-0000-4000-8000-000000000003',
    title: '治愈系收集',
    slug: 'cozy-collect',
    play_count: 456,
    published_at: '2026-07-18T16:00:00Z',
    author_display: 'GameForge',
  },
]

async function tryFetchPublic(): Promise<PublicGame[] | null> {
  const res = await fetch(`${env.apiBaseUrl}/games/public`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) return null
  const json = (await res.json()) as { data?: PublicGame[] }
  if (!json.data || !Array.isArray(json.data)) return null
  return json.data
}

export const publicGamesApi = {
  /** 真实 API 可用时用真实数据；否则 Mock（B2 联调前） */
  async list(): Promise<PublicGame[]> {
    if (import.meta.env.VITE_PUBLIC_GAMES_MOCK === 'true') {
      return MOCK_PUBLIC_GAMES
    }
    try {
      const live = await tryFetchPublic()
      if (live && live.length > 0) return live
    } catch {
      /* fallback */
    }
    return MOCK_PUBLIC_GAMES
  },
}

export { MOCK_PUBLIC_GAMES }
