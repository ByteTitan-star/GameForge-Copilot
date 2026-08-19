import { describe, expect, it } from 'vitest'
import {
  groupChatMessages,
  isLongChatMessage,
  LONG_CHAT_MESSAGE_CHARS,
  type ChatMsg,
} from './chat-blocks'

const msg = (id: string, kind: ChatMsg['kind'], content: string): ChatMsg => ({
  id,
  role: 'assistant',
  content,
  kind,
})

describe('groupChatMessages', () => {
  it('把连续 thinking 收成一块，正文仍分开', () => {
    const blocks = groupChatMessages([
      msg('1', 'thinking', '正在构思玩法与策划稿…'),
      msg('2', 'thinking', '正在设计视觉方案…'),
      msg('3', 'design', '# 策划稿'),
      msg('4', 'completed', '# 任务执行已完成'),
    ])
    expect(blocks).toHaveLength(3)
    expect(blocks[0]).toMatchObject({ type: 'thinking' })
    if (blocks[0].type === 'thinking') {
      expect(blocks[0].items).toHaveLength(2)
    }
    expect(blocks[1]).toMatchObject({ type: 'message' })
    expect(blocks[2]).toMatchObject({ type: 'message' })
  })
})

describe('isLongChatMessage', () => {
  it('短消息不折叠', () => {
    expect(isLongChatMessage('做个侧视物理越野车')).toBe(false)
  })

  it('超过阈值才算长消息', () => {
    expect(isLongChatMessage('侧'.repeat(LONG_CHAT_MESSAGE_CHARS))).toBe(false)
    expect(isLongChatMessage('侧'.repeat(LONG_CHAT_MESSAGE_CHARS + 1))).toBe(true)
  })
})
