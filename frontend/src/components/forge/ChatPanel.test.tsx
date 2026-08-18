import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatPanel } from './ChatPanel'
import type { ChatMsg } from './chat-blocks'

afterEach(cleanup)

const baseProps = {
  messages: [] as const,
  input: '还能发吗',
  onInputChange: () => undefined,
  onSend: vi.fn(),
}

describe('ChatPanel HITL 底栏', () => {
  it('无覆盖时展示底栏输入框', () => {
    render(<ChatPanel {...baseProps} />)
    expect(screen.getByRole('textbox', { name: '例如：再难一点，背景换成夜景…' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '发送需求' })).toBeInTheDocument()
  })

  it('HITL 覆盖底栏输入框，用户无法继续发消息', () => {
    render(<ChatPanel {...baseProps} composerCover={<div>人工确认卡</div>} />)
    expect(screen.getByText('人工确认卡')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '例如：再难一点，背景换成夜景…' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '发送需求' })).not.toBeInTheDocument()
  })
})

describe('ChatPanel thinking 与 Markdown 正文', () => {
  const thinking: ChatMsg = {
    id: 't1',
    role: 'assistant',
    kind: 'thinking',
    content: '正在构思玩法与策划稿…',
  }
  const design: ChatMsg = {
    id: 'd1',
    role: 'assistant',
    kind: 'design',
    content: '# 霓虹躲避',
  }

  it('运行中最后一块是 thinking 时展开过程', () => {
    render(<ChatPanel {...baseProps} messages={[thinking]} streaming />)
    expect(screen.queryByRole('button', { name: /正在思考/ })).not.toBeInTheDocument()
    expect(screen.getByText('正在思考…')).toBeInTheDocument()
    expect(screen.getByText('正在构思玩法与策划稿…')).toBeInTheDocument()
    expect(screen.getByTestId('thinking-skeleton')).toBeInTheDocument()
  })

  it('正文出现后思考过程默认折叠，仍可展开', () => {
    render(<ChatPanel {...baseProps} messages={[thinking, design]} />)
    expect(screen.getByRole('heading', { name: '霓虹躲避' })).toBeInTheDocument()
    expect(screen.queryByText('正在构思玩法与策划稿…')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '思考过程' }))
    expect(screen.getByText('正在构思玩法与策划稿…')).toBeInTheDocument()
  })
})

describe('ChatPanel 可读性与生成中态', () => {
  it('用户开口后只隐藏开场欢迎语，不丢历史助手消息', () => {
    render(
      <ChatPanel
        {...baseProps}
        messages={[
          { id: 'm0', role: 'assistant', content: '直接说你想玩的规则。生成后可以马上试，也可以继续改。' },
          { id: 'a1', role: 'assistant', content: '已更新关卡难度。' },
          { id: 'u1', role: 'user', content: '再难一点' },
        ]}
      />,
    )
    expect(screen.queryByText(/直接说你想玩的规则/)).not.toBeInTheDocument()
    expect(screen.getByText('已更新关卡难度。')).toBeInTheDocument()
    expect(screen.getByText('再难一点')).toBeInTheDocument()
  })

  it('尚无用户消息时仍展示开场欢迎语', () => {
    render(
      <ChatPanel
        {...baseProps}
        messages={[
          { id: 'm0', role: 'assistant', content: '直接说你想玩的规则。生成后可以马上试，也可以继续改。' },
        ]}
      />,
    )
    expect(screen.getByText(/直接说你想玩的规则/)).toBeInTheDocument()
  })

  it('用户气泡限制阅读宽度', () => {
    render(
      <ChatPanel
        {...baseProps}
        messages={[{ id: 'u1', role: 'user', content: '做个赛车' }]}
      />,
    )
    const row = screen.getByText('做个赛车').closest('[data-chat-row]')
    expect(row?.className).toMatch(/max-w-\[min\(42rem,85%\)\]/)
  })

  it('超长用户消息默认折叠，可展开', () => {
    const long = `做一款2D侧视物理越野车。${'坡道、悬崖、吊桥、燃料、金币。'.repeat(20)}`
    render(
      <ChatPanel
        {...baseProps}
        messages={[{ id: 'u1', role: 'user', content: long }]}
      />,
    )
    const expand = screen.getByRole('button', { name: '展开' })
    expect(expand).toBeInTheDocument()
    expect(expand.previousElementSibling).toHaveClass('line-clamp-6')
    fireEvent.click(expand)
    expect(screen.getByRole('button', { name: '收起' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '展开' })).not.toBeInTheDocument()
  })

  it('生成中输入框改成等待文案，发送键禁用且无渐变', () => {
    render(
      <ChatPanel
        {...baseProps}
        input=""
        messages={[
          {
            id: 't1',
            role: 'assistant',
            kind: 'thinking',
            content: '正在构思玩法与策划稿…',
          },
        ]}
        streaming
        disabled
        sendDisabled
      />,
    )
    const box = screen.getByRole('textbox', { name: '生成中，请稍候…' })
    expect(box).toBeDisabled()
    const send = screen.getByRole('button', { name: '生成中，请稍候…' })
    expect(send).toBeDisabled()
    expect(send.className).not.toMatch(/linear-gradient/)
  })
})
