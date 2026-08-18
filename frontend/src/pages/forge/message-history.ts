import type { ChatMsg } from '@/components/forge/ChatPanel'
import type { ForgeMessage } from '@/api/types'

export function toChatMessages(rows: ForgeMessage[]): ChatMsg[] {
  return rows.map((row) => {
    const node =
      row.metadata && typeof row.metadata === 'object' && 'node' in row.metadata
        ? String((row.metadata as { node?: unknown }).node || '')
        : ''
    const persistenceKey = row.run_id
      ? row.kind === 'design'
        ? `${row.run_id}:design`
        : node
          ? `${row.run_id}:${row.kind}:${node}`
          : `${row.run_id}:${row.kind}`
      : undefined
    const kind =
      row.kind === 'design' || row.kind === 'completed' ? row.kind : 'chat'
    return {
      id: row.message_id,
      role: row.role,
      content: row.content,
      persistenceKey,
      kind,
    }
  })
}

export function mergeChatMessages(current: ChatMsg[], incoming: ChatMsg[]): ChatMsg[] {
  const incomingIds = new Set(incoming.map((message) => message.id))
  const incomingKeys = new Set(
    incoming.flatMap((message) => (message.persistenceKey ? [message.persistenceKey] : [])),
  )
  const incomingContent = new Set(
    incoming.map((message) => `${message.role}:${message.content}`),
  )
  const localOnly = current.filter(
    (message) =>
      message.id !== 'm0' &&
      !incomingIds.has(message.id) &&
      (!message.persistenceKey || !incomingKeys.has(message.persistenceKey)) &&
      !incomingContent.has(`${message.role}:${message.content}`),
  )
  return [...incoming, ...localOnly]
}
