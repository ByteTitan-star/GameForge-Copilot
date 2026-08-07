import { describe, expect, it } from 'vitest'
import { draftArtifactUrl, playArtifactUrl, resolveHostingUrl, wsRunUrl } from './hosting'

describe('hosting URL helpers', () => {
  it('试玩与草稿 URL 指向托管根', () => {
    expect(playArtifactUrl('pixel-runner')).toMatch(/\/play\/pixel-runner$/)
    expect(draftArtifactUrl('g-1', 2)).toMatch(/\/draft\/g-1\/2$/)
  })

  it('相对 preview_url 解析到 hosting 根', () => {
    expect(resolveHostingUrl('/draft/g-1/3')).toMatch(/\/draft\/g-1\/3$/)
    expect(resolveHostingUrl('https://cdn.example/play/x')).toBe('https://cdn.example/play/x')
  })

  it('WS run URL 带 token 查询参数', () => {
    const url = wsRunUrl('run-abc', 'tok-1')
    expect(url).toMatch(/\/ws\/runs\/run-abc\?token=tok-1$/)
    expect(url.startsWith('ws')).toBe(true)
  })
})
