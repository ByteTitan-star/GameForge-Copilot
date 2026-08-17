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

describe('HitlCard plan review', () => {
  const planPayload = {
    node: 'plan_confirm',
    design_doc: {
      title: '霓虹躲避',
      gameplay: '玩家控制发光核心躲避几何体',
      controls: ['WASD 移动', 'P 暂停'],
      levels: ['觉醒'],
      core_loop: ['躲避敌人'],
    },
    action_url: '/hitl/resolve',
  }

  it('用 Markdown 展示策划稿，不再用玩法/操作字段表单', () => {
    render(<HitlCard payload={planPayload} onResolve={vi.fn()} onReject={vi.fn()} />)
    expect(screen.getByRole('heading', { name: '霓虹躲避' })).toBeInTheDocument()
    expect(screen.getByText('玩家控制发光核心躲避几何体')).toBeInTheDocument()
    expect(screen.getByText('WASD 移动')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '玩法' })).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '操作' })).not.toBeInTheDocument()
  })

  it('批准提交原始策划稿；修改意见走输入框', () => {
    const onResolve = vi.fn()
    render(<HitlCard payload={planPayload} onResolve={onResolve} onReject={vi.fn()} />)
    fireEvent.click(screen.getByText('批准继续'))
    expect(onResolve).toHaveBeenCalledWith('approve', null, planPayload.design_doc)

    fireEvent.change(screen.getByRole('textbox', { name: '修改意见（可选）' }), {
      target: { value: '暂停要更明显' },
    })
    fireEvent.click(screen.getByText('批准继续'))
    expect(onResolve).toHaveBeenLastCalledWith('modify', '暂停要更明显', planPayload.design_doc)
  })
})
