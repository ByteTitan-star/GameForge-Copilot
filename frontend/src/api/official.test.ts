import { afterEach, describe, expect, it, vi } from 'vitest'
import { officialApi } from './official'

describe('officialApi.list', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('网络失败时抛错而非返回 Mock', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(officialApi.list()).rejects.toThrow()
  })
})
