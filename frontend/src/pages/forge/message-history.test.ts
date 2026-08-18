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

  it('HITL 消息去重键包含 node，避免多段确认撞车', () => {
    expect(
      toChatMessages([
        row({
          kind: 'hitl_approve',
          content: '已确认设计方案',
          metadata: { node: 'plan_confirm', decision: 'approve' },
        }),
      ])[0].persistenceKey,
    ).toBe('run-1:hitl_approve:plan_confirm')
  })

  it('同一 run 的策划稿共用去重键，冲掉打字机临时稿', () => {
    const streamed: ChatMsg[] = [
      {
        id: 'streaming-run-1',
        role: 'assistant',
        kind: 'design',
        content: '# 霓虹躲避',
        persistenceKey: 'run-1:design',
      },
    ]
    const incoming = toChatMessages([
      row({
        message_id: 'server-design',
        role: 'assistant',
        kind: 'design',
        content: '# 霓虹躲避\n\n请确认方案，或填写修改意见。',
        metadata: { node: 'plan_confirm' },
      }),
    ])
    expect(incoming[0].persistenceKey).toBe('run-1:design')
    expect(mergeChatMessages(streamed, incoming)).toEqual(incoming)
  })

  it('design/completed 映射到对话 kind', () => {
    expect(toChatMessages([row({ role: 'assistant', kind: 'design' })])[0].kind).toBe('design')
    expect(toChatMessages([row({ role: 'assistant', kind: 'completed' })])[0].kind).toBe(
      'completed',
    )
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
