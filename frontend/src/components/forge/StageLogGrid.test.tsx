import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { RunPhase } from '@/api/enums'
import { emptyStagePipeline } from '@/lib/stage-pipeline-state'
import { StageLogGrid } from './StageLogGrid'

afterEach(cleanup)

describe('StageLogGrid 行布局', () => {
  it('标题与时间同一行，详情在第二行', () => {
    render(
      <StageLogGrid
        runPhase={RunPhase.plan}
        stages={emptyStagePipeline()}
        items={[
          {
            id: 'ev-1',
            label: '等待人工确认',
            detail: 'nego Dodge',
            tone: 'warn',
            at: '2026-08-17T14:15:44.000Z',
            phase: RunPhase.plan,
          },
        ]}
      />,
    )

    const label = screen.getByText('等待人工确认')
    const detail = screen.getByText('nego Dodge')
    const time = label.parentElement?.querySelector('time')
    expect(time).toBeTruthy()
    expect(label.parentElement).toContainElement(time!)
    expect(label.parentElement).not.toContainElement(detail)
    expect(detail.parentElement).toContainElement(label.parentElement!)
  })

  it('当前阶段列使用轻量高亮，不依赖可见滚动条', () => {
    const stages = emptyStagePipeline()
    stages[RunPhase.art] = { status: 'active' }
    const { container } = render(
      <StageLogGrid runPhase={RunPhase.art} stages={stages} items={[]} />,
    )
    const cols = container.querySelectorAll('.gf-forge-stage-log-col')
    expect(cols[1]).toHaveClass('is-active')
    expect(cols[0]).not.toHaveClass('is-active')
    expect(cols[2]).not.toHaveClass('is-active')
    expect(container.querySelector('.gf-forge-stage-log-col-list')).toBeInTheDocument()
  })
})
