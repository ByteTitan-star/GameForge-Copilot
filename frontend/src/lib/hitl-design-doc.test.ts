import { describe, expect, it } from 'vitest'
import { isFailureHitlNode, parseDesignDoc, parseHitlFailure } from '@/lib/hitl-design-doc'

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

  it('detects failure nodes', () => {
    expect(isFailureHitlNode('sandbox_failed')).toBe(true)
    expect(isFailureHitlNode('plan_confirm')).toBe(false)
  })

  it('collects error lines from payload', () => {
    const extra = parseHitlFailure({
      error: 'build failed',
      issues: ['missing index.html'],
    })
    expect(extra.errors).toContain('build failed')
    expect(extra.issues).toContain('missing index.html')
  })
})
