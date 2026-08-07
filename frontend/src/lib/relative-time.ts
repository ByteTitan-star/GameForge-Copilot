import { messages } from '@/i18n/messages'
import type { Locale } from '@/stores/locale-store'

/** Relative time; absolute time still available via title/tooltip */
export function formatRelativeTime(iso: string, locale: Locale, now = Date.now()): string {
  const m = messages[locale]
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return iso
  const diff = Math.max(0, now - t)
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return m.relativeJustNow
  const min = Math.floor(sec / 60)
  if (min < 60) return m.relativeMinutes.replace('{n}', String(min))
  const hr = Math.floor(min / 60)
  if (hr < 24) return m.relativeHours.replace('{n}', String(hr))
  const day = Math.floor(hr / 24)
  if (day < 30) return m.relativeDays.replace('{n}', String(day))
  return new Date(iso).toLocaleDateString(locale === 'zh' ? 'zh-CN' : 'en-US')
}
