export type ChatKind = 'chat' | 'thinking' | 'design' | 'completed'

export type ChatMsg = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  persistenceKey?: string
  kind?: ChatKind
}

export type ChatBlock =
  | { type: 'message'; msg: ChatMsg }
  | { type: 'thinking'; id: string; items: ChatMsg[] }

/** 超过约 6 行中文时折叠，避免全宽气泡变成墙。 */
export const LONG_CHAT_MESSAGE_CHARS = 240

export function isLongChatMessage(content: string): boolean {
  return content.trim().length > LONG_CHAT_MESSAGE_CHARS
}

export function groupChatMessages(messages: ChatMsg[]): ChatBlock[] {
  const blocks: ChatBlock[] = []
  for (const msg of messages) {
    if (msg.kind === 'thinking') {
      const last = blocks[blocks.length - 1]
      if (last?.type === 'thinking') {
        last.items.push(msg)
      } else {
        blocks.push({ type: 'thinking', id: `think-${msg.id}`, items: [msg] })
      }
      continue
    }
    blocks.push({ type: 'message', msg })
  }
  return blocks
}
