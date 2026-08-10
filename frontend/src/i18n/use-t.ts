import { useLocaleStore } from '@/stores/locale-store'
import { messages, type MessageKey } from './messages'

export function useT() {
  const locale = useLocaleStore((s) => s.locale)
  return (key: MessageKey, params?: Record<string, string | number>) => {
    const template = messages[locale][key]
    if (!params) return template
    return template.replace(/\{(\w+)\}/g, (_, name) =>
      params[name] !== undefined ? String(params[name]) : `{${name}}`,
    )
  }
}
