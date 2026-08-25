import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { RunPhase } from '@/api/enums'
import { emptyStagePipeline } from '@/lib/stage-pipeline-state'
import { ForgeLogDock } from './ForgeLogDock'

afterEach(() => {
  cleanup()
  localStorage.removeItem('gf-forge-log-height')
})

describe('ForgeLogDock', () => {
  it('展开时阶段条在滚动区外，事件流单独滚动', () => {
    const items = Array.from({ length: 12 }, (_, index) => ({
      id: `event-${index}`,
      label: `事件 ${index}`,
      tone: 'info' as const,
      at: '2026-08-13T00:00:00Z',
    }))
    const { container } = render(
      <ForgeLogDock
        open
        onToggle={() => undefined}
        runPhase={RunPhase.code}
        stages={emptyStagePipeline()}
        items={items}
      />,
    )

    const scroll = container.querySelector('.gf-forge-log-dock-scroll')
    expect(scroll).toBeInTheDocument()
    expect(screen.getByLabelText('生成流程')).toBeInTheDocument()
    expect(screen.getByText('事件 11')).toBeInTheDocument()
    fireEvent.wheel(scroll!, { deltaY: 200 })
  })

  it('HITL 共存时加上安全高度 class，避免日志带过高', () => {
    localStorage.setItem('gf-forge-log-height', String(Math.round(window.innerHeight * 0.5)))
    const { container } = render(
      <ForgeLogDock
        open
        reserveForHitl
        onToggle={() => undefined}
        runPhase={RunPhase.plan}
        stages={emptyStagePipeline()}
        items={[]}
      />,
    )
    const dock = container.querySelector('.gf-forge-log-dock')
    expect(dock).toHaveClass('gf-forge-log-dock--hitl-safe')
  })
})
