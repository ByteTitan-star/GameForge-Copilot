import { afterEach, describe, expect, it, vi } from 'vitest'
import { publicGamesApi } from '@/api/public-games'

describe('publicGamesApi', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('网络失败时抛错而非返回 Mock', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(publicGamesApi.list()).rejects.toThrow()
  })
})
