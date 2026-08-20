import { useCallback } from 'react'
import { useLocaleStore } from '@/stores/locale-store'
import { messages, type MessageKey } from './messages'

export function useT() {
  const locale = useLocaleStore((s) => s.locale)
  // 必须稳定：否则把 t 放进 useEffect deps 会形成「setState → 新 t → 再 effect」死循环
  // （典型症状：preview-token 一秒打几百次）。
  return useCallback(
    (key: MessageKey, params?: Record<string, string | number>) => {
      const template = messages[locale][key]
      if (!params) return template
      return template.replace(/\{(\w+)\}/g, (_, name) =>
        params[name] !== undefined ? String(params[name]) : `{${name}}`,
      )
    },
    [locale],
  )
}
