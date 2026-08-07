import { describe, expect, it } from 'vitest'
import { getTemplateById, GAME_TEMPLATES } from '@/constants/templates'

describe('game templates', () => {
  it('includes snake template with seed', () => {
    const snake = getTemplateById('snake')
    expect(snake?.requirement_seed).toMatch(/贪吃蛇/)
  })

  it('has four presets', () => {
    expect(GAME_TEMPLATES).toHaveLength(4)
  })
})
