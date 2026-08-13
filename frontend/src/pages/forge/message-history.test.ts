import { describe, expect, it } from 'vitest'

import type { ForgeMessage } from '@/api/types'
import type { ChatMsg } from '@/components/forge/ChatPanel'
import { mergeChatMessages, toChatMessages } from './message-history'

const row = (overrides: Partial<ForgeMessage> = {}): ForgeMessage => ({
  message_id: 'server-1',
  game_id: 'game-1',
  run_id: 'run-1',
  role: 'user',
  kind: 'requirement',
  content: '做一个平台跳跃游戏',
  metadata: {},
  created_at: '2026-08-13T00:00:00Z',
  ...overrides,
})

describe('forge message history', () => {
  it('为持久消息生成业务去重键', () => {
    expect(toChatMessages([row()])[0]).toMatchObject({
      id: 'server-1',
      persistenceKey: 'run-1:requirement',
    })
  })

  it('服务端历史替换同业务键或同内容的临时消息', () => {
    const local: ChatMsg[] = [
      { id: 'local-1', role: 'user', content: '做一个平台跳跃游戏' },
      {
        id: 'local-2',
        role: 'assistant',
        content: '本地完成提示',
        persistenceKey: 'run-1:completed',
      },
    ]
    const incoming = toChatMessages([
      row(),
      row({
        message_id: 'server-2',
        role: 'assistant',
        kind: 'completed',
        content: '游戏已完成',
      }),
    ])
    expect(mergeChatMessages(local, incoming)).toEqual(incoming)
  })
})
