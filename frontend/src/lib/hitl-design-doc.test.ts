import { describe, expect, it } from 'vitest'
import { designDocToMarkdown, parseDesignDoc } from '@/lib/hitl-design-doc'

describe('hitl design doc parser', () => {
  it('parses string design_doc as gameplay', () => {
    const doc = parseDesignDoc('方向键贪吃蛇', '霓虹蛇')
    expect(doc.gameplay).toContain('贪吃蛇')
    expect(doc.title).toBe('霓虹蛇')
  })

  it('parses structured object with level objects', () => {
    const doc = parseDesignDoc(
      {
        title: 'TD',
        gameplay: '放塔',
        controls: '鼠标',
        levels: [{ name: 'wave-1' }, 'wave-2'],
      },
      'fallback',
    )
    expect(doc.levels).toEqual(['wave-1', 'wave-2'])
  })

  it('把策划稿转成可读 Markdown', () => {
    const text = designDocToMarkdown({
      title: '霓虹躲避',
      gameplay: '玩家控制发光核心躲避几何体',
      controls: ['WASD 移动', 'P 暂停'],
      levels: ['觉醒'],
      core_loop: ['躲避敌人'],
    })
    expect(text).toContain('# 霓虹躲避')
    expect(text).toContain('## 玩法概述')
    expect(text).toContain('- WASD 移动')
    expect(text).toContain('1. 躲避敌人')
  })
})

describe('hitl design doc parser', () => {
  it('parses string design_doc as gameplay', () => {
    const doc = parseDesignDoc('方向键贪吃蛇', '霓虹蛇')
    expect(doc.gameplay).toContain('贪吃蛇')
    expect(doc.title).toBe('霓虹蛇')
  })

  it('parses structured object with level objects', () => {
    const doc = parseDesignDoc(
      {
        title: 'TD',
        gameplay: '放塔',
        controls: '鼠标',
        levels: [{ name: 'wave-1' }, 'wave-2'],
      },
      'fallback',
    )
    expect(doc.levels).toEqual(['wave-1', 'wave-2'])
  })
})
