import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ForgeAiStatusBar } from './ForgeAiStatusBar'

afterEach(cleanup)

describe('ForgeAiStatusBar', () => {
  it('生成中只展示状态文案，右侧没有假按钮', () => {
    render(
      <ForgeAiStatusBar
        status={{
          level: 'running',
          labelKey: 'building',
          tone: 'amber',
          canSend: false,
          blocked: false,
        }}
      />,
    )
    expect(screen.getByText('需求对话')).toBeInTheDocument()
    expect(screen.getByText('生成中')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
