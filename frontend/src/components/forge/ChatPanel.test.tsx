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
    expect(screen.getByRole('button', { name: /正在思考/ })).toBeInTheDocument()
    expect(screen.getByText('正在构思玩法与策划稿…')).toBeInTheDocument()
  })

  it('正文出现后思考过程默认折叠，仍可展开', () => {
    render(<ChatPanel {...baseProps} messages={[thinking, design]} />)
    expect(screen.getByRole('heading', { name: '霓虹躲避' })).toBeInTheDocument()
    expect(screen.queryByText('正在构思玩法与策划稿…')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '思考过程' }))
    expect(screen.getByText('正在构思玩法与策划稿…')).toBeInTheDocument()
  })
})
