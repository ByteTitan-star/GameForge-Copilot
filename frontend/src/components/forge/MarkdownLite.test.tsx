import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MarkdownLite } from './MarkdownLite'

afterEach(cleanup)

describe('MarkdownLite', () => {
  it('渲染标题与列表', () => {
    render(
      <MarkdownLite
        text={'# 任务执行已完成\n\n## 怎么玩\n- WASD 移动\n1. 躲避敌人'}
      />,
    )
    expect(screen.getByRole('heading', { level: 3, name: '任务执行已完成' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 4, name: '怎么玩' })).toBeInTheDocument()
    expect(screen.getByText('WASD 移动')).toBeInTheDocument()
    expect(screen.getByText('躲避敌人')).toBeInTheDocument()
  })
})
