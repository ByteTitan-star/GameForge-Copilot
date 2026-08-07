import { env } from '@/lib/env'
import { apiRequest } from './client'
import type { CreateGameResponse } from './types'

export type OfficialGame = {
  slug: string
  title: string
  description: string
  play_url: string
  thumbnail_url: string | null
}

const MOCK_OFFICIAL: OfficialGame[] = [
  {
    slug: 'official-neon-snake',
    title: '霓虹贪吃蛇',
    description: '方向键控制，吃豆加分，经典街机手感。',
    play_url: '/play/official-neon-snake',
    thumbnail_url: null,
  },
  {
    slug: 'official-pixel-run',
    title: '像素跑酷',
    description: '跳跃躲避障碍，收集金币，难度递增。',
    play_url: '/play/official-pixel-run',
    thumbnail_url: null,
  },
  {
    slug: 'official-tower-sketch',
    title: '塔防雏形',
    description: '放置炮塔，抵御多波怪物进攻。',
    play_url: '/play/official-tower-sketch',
    thumbnail_url: null,
  },
]

async function tryFetchOfficial(): Promise<OfficialGame[] | null> {
  const res = await fetch(`${env.apiBaseUrl}/official-games`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) return null
  const json = (await res.json()) as { data?: OfficialGame[] }
  if (!json.data?.length) return null
  return json.data
}

export const officialApi = {
  /** B-A2 未写入 openapi 前可 Mock；联调后走真实 GET /official-games */
  async list(): Promise<OfficialGame[]> {
    try {
      const live = await tryFetchOfficial()
      if (live?.length) return live
      return await apiRequest<OfficialGame[]>('/official-games')
    } catch {
      return MOCK_OFFICIAL
    }
  },

  /** POST /games/fork/{slug} — 待契约冻结；404 时抛错由 UI toast */
  fork(slug: string, accessToken: string) {
    return apiRequest<CreateGameResponse>(`/games/fork/${encodeURIComponent(slug)}`, {
      method: 'POST',
      token: accessToken,
      body: {},
    })
  },
}

export { MOCK_OFFICIAL }
