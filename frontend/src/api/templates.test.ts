import { describe, expect, it, vi } from 'vitest'
import { templatesApi, templateEmoji } from './templates'

describe('templatesApi', () => {
  it('returns API rows when available', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          data: [
            {
              template_id: 'survival-dodge',
              title: '极限生存躲避',
              description: 'demo',
              requirement_seed: 'seed',
              tags: ['arcade'],
              engine: 'canvas',
              playable: false,
              play_url: null,
            },
          ],
        }),
      }),
    )
    const list = await templatesApi.list()
    expect(list).toHaveLength(1)
    expect(list[0]!.template_id).toBe('survival-dodge')
    expect(templateEmoji(list[0]!.template_id, list[0]!.tags)).toBe('🕹️')
  })

  it('returns empty list when API unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, json: async () => null }),
    )
    const list = await templatesApi.list()
    expect(list).toEqual([])
  })
})
