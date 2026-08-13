import type { ChatMsg } from '@/components/forge/ChatPanel'
import type { ForgeMessage } from '@/api/types'

export function toChatMessages(rows: ForgeMessage[]): ChatMsg[] {
  return rows.map((row) => ({
    id: row.message_id,
    role: row.role,
    content: row.content,
    persistenceKey: row.run_id ? `${row.run_id}:${row.kind}` : undefined,
  }))
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
