import { describe, expect, it, vi } from 'vitest'
import { templatesApi, templateEmoji } from './templates'

describe('templatesApi', () => {
  it('falls back when API unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, json: async () => null }),
    )
    const list = await templatesApi.list()
    expect(list.length).toBeGreaterThan(0)
    expect(templateEmoji(list[0]!.template_id)).toBeTruthy()
  })
})
