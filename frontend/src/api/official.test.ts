import { afterEach, describe, expect, it, vi } from 'vitest'
import { MOCK_OFFICIAL, officialApi } from './official'

describe('officialApi.list', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('falls back to mock when network fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const list = await officialApi.list()
    expect(list.length).toBe(MOCK_OFFICIAL.length)
    expect(list[0]?.slug).toBe(MOCK_OFFICIAL[0]?.slug)
  })
})
