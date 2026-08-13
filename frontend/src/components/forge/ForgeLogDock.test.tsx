import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RunPhase } from '@/api/enums'
import { emptyStagePipeline } from '@/lib/stage-pipeline-state'
import { ForgeLogDock } from './ForgeLogDock'

describe('ForgeLogDock', () => {
  it('展开时使用单一滚动容器，并以紧凑阶段条展示事件', () => {
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
    expect(scroll?.querySelectorAll('.gf-forge-log-dock-scroll')).toHaveLength(0)
    expect(screen.getByRole('list', { name: '生成流程' })).toBeInTheDocument()
    expect(screen.getByText('事件 11')).toBeInTheDocument()
    fireEvent.wheel(scroll!, { deltaY: 200 })
  })
})
