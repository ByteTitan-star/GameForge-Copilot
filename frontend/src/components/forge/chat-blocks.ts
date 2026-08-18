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
