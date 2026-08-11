import { describe, expect, it } from 'vitest'
import { officialCoverUrl } from './official-covers'

describe('officialCoverUrl', () => {
  it('官方三款 slug 返回对应封面图路径', () => {
    expect(officialCoverUrl('official-neon-snake')).toMatch(
      /official\/official-neon-snake\.png$/,
    )
    expect(officialCoverUrl('official-pixel-runner')).toMatch(
      /official\/official-pixel-runner\.png$/,
    )
    expect(officialCoverUrl('official-tower-stub')).toMatch(
      /official\/official-tower-stub\.png$/,
    )
  })

  it('非官方游戏 slug 返回 null（前端回退渐变封面）', () => {
    expect(officialCoverUrl('user-snake-xxx')).toBeNull()
    expect(officialCoverUrl('')).toBeNull()
  })
})
