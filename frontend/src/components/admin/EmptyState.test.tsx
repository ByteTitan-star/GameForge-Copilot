import { describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach } from 'vitest'
import { Package } from 'lucide-react'
import { EmptyState } from './EmptyState'

afterEach(cleanup)

/**
 * 后台空状态冒烟测试。保护 P1-4：空状态带图标 + 标题 + 描述 + 可选 CTA，
 * 取代旧的一行冷文字。action 槽是 PublishedSection「去发现页」引导的落点，
 * 必须稳定渲染。
 */
describe('EmptyState', () => {
  it('渲染图标 + 标题 + 描述', () => {
    render(<EmptyState icon={Package} title="暂无已发布游戏" description="还没有作品通过审核" />)
    expect(screen.getByText('暂无已发布游戏')).toBeInTheDocument()
    expect(screen.getByText('还没有作品通过审核')).toBeInTheDocument()
    // icon 容器存在（lucide 渲染为 svg）
    expect(document.querySelector('.gf-empty-icon-wrap')).toBeInTheDocument()
  })

  it('传入 action 时渲染 CTA（保护空状态引导不丢）', () => {
    render(
      <EmptyState icon={Package} title="暂无数据" action={<a href="/discover">去发现页</a>} />,
    )
    const cta = screen.getByText('去发现页')
    expect(cta).toBeInTheDocument()
    expect(cta).toHaveAttribute('href', '/discover')
  })

  it('无 description / action 时仅渲染标题，不报错', () => {
    render(<EmptyState title="暂无审批单据" />)
    expect(screen.getByText('暂无审批单据')).toBeInTheDocument()
    expect(screen.queryByText('去发现页')).not.toBeInTheDocument()
  })
})
