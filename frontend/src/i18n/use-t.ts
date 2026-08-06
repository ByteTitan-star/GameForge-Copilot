import { useLocaleStore } from '@/stores/locale-store'
import { messages, type MessageKey } from './messages'

export function useT() {
  const locale = useLocaleStore((s) => s.locale)
  return (key: MessageKey) => messages[locale][key]
}
