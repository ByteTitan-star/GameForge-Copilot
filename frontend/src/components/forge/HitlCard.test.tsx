import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HitlCard } from './HitlCard'

const payload = {
  node: 'art_confirm',
  design_doc: { title: '霓虹蛇', gameplay: '移动收集', controls: '方向键移动', levels: [] },
  action_url: '/hitl/resolve',
  art_options: {
    options: [
      { id: 'A' as const, name: '清透霓虹', summary: 'Canvas 粒子与轨迹', recommended: true },
      { id: 'B' as const, name: '纸雕街机', summary: 'CSS 纸片与硬边阴影', recommended: false },
    ],
  },
}

afterEach(cleanup)

describe('HitlCard art review', () => {
  it('展示两个方案、推荐项并提交选择', () => {
    const onResolve = vi.fn()
    render(<HitlCard payload={payload} onResolve={onResolve} onReject={vi.fn()} />)
    expect(screen.getByText(/清透霓虹/)).toBeInTheDocument()
    expect(screen.getByText(/纸雕街机/)).toBeInTheDocument()
    expect(screen.getByText('推荐')).toBeInTheDocument()
    fireEvent.click(screen.getAllByText('选择此方向')[0])
    fireEvent.click(screen.getByText('选择此方向 · A'))
    expect(onResolve).toHaveBeenCalledWith('select_a')
  })

  it('携带反馈重新生成两个方案', () => {
    const onResolve = vi.fn()
    render(<HitlCard payload={payload} onResolve={onResolve} onReject={vi.fn()} />)
    fireEvent.change(screen.getByRole('textbox', { name: '希望下一组方案如何调整' }), {
      target: { value: '更克制，减少粒子' },
    })
    fireEvent.click(screen.getByText('重新生成方案'))
    expect(onResolve).toHaveBeenCalledWith('modify', '更克制，减少粒子')
  })
})
