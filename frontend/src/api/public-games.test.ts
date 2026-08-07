import { describe, expect, it } from 'vitest'
import { MOCK_PUBLIC_GAMES, publicGamesApi } from '@/api/public-games'

describe('publicGamesApi', () => {
  it('后端未就绪时返回 Mock 数据', async () => {
    const games = await publicGamesApi.list()
    expect(games.length).toBeGreaterThanOrEqual(3)
    expect(games[0]?.slug).toBe(MOCK_PUBLIC_GAMES[0]?.slug)
  })
})
