import { describe, expect, it } from 'vitest'
import {
  draftArtifactUrl,
  isPreviewTokenUrl,
  playArtifactUrl,
  resolveHostingUrl,
  templatePlayUrl,
  wsRunUrl,
} from './hosting'

describe('hosting URL helpers', () => {
  it('试玩与草稿 URL 指向托管根', () => {
    // dev 环境 artifact URL 会带 ?v= 时间戳破强缓存（见 hosting.ts），正则需允许该后缀
    expect(playArtifactUrl('pixel-runner')).toMatch(/\/play\/pixel-runner(\?v=\d+)?$/)
    expect(draftArtifactUrl('g-1', 2)).toMatch(/\/draft\/g-1\/2(\?v=\d+)?$/)
    expect(templatePlayUrl('survival-dodge')).toMatch(
      /\/play\/template\/survival-dodge(\?v=\d+)?$/,
    )
  })

  it('相对 preview_url 解析到 hosting 根', () => {
    expect(resolveHostingUrl('/draft/g-1/3')).toMatch(/\/draft\/g-1\/3$/)
    expect(resolveHostingUrl('/preview/tok/g-1/3/')).toMatch(/\/preview\/tok\/g-1\/3\/$/)
    expect(resolveHostingUrl('https://cdn.example/play/x')).toBe('https://cdn.example/play/x')
  })

  it('isPreviewTokenUrl 识别 preview token 路径', () => {
    expect(isPreviewTokenUrl('http://127.0.0.1:8000/preview/tok/g/1/')).toBe(true)
    expect(isPreviewTokenUrl('http://127.0.0.1:8000/draft/g/1')).toBe(false)
  })

  it('WS run URL 带 token 查询参数', () => {
    const url = wsRunUrl('run-abc', 'tok-1')
    expect(url).toMatch(/\/ws\/runs\/run-abc\?token=tok-1$/)
    expect(url.startsWith('ws')).toBe(true)
  })
})
