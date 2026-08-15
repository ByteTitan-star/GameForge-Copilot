import { useEffect, useState } from 'react'
import { normalizeHex } from '@/lib/theme/color-utils'
import type { ThemeColors } from '@/lib/theme/types'
import { useT } from '@/i18n/use-t'

type ColorKey = keyof ThemeColors

type Props = {
  colorKey: ColorKey
  label: string
  hint: string
  value: string
  onCommit: (key: ColorKey, normalized: string) => void
}

export function CustomColorField({ colorKey, label, hint, value, onCommit }: Props) {
  const t = useT()
  const [draft, setDraft] = useState(value)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDraft(value)
    setError(null)
  }, [value])

  function commitDraft(raw: string) {
    const normalized = normalizeHex(raw)
    if (!normalized) {
      setError(t('themeInvalidColor'))
      setDraft(value)
      return
    }
    setError(null)
    setDraft(normalized)
    if (normalized !== value) onCommit(colorKey, normalized)
  }

  return (
    <label className="space-y-1.5">
      <span className="gf-page-muted block text-xs">{label}</span>
      <div className="gf-border-subtle flex items-center gap-2 rounded-xl bg-black/[0.02] p-2 ring-1 ring-[var(--gf-border)]">
        <input
          type="color"
          value={value}
          onChange={(e) => onCommit(colorKey, normalizeHex(e.target.value) ?? value)}
          className="gf-color-swatch h-10 w-10 shrink-0 cursor-pointer rounded-lg border-0 bg-transparent p-0"
          aria-label={label}
        />
        <div className="min-w-0">
          <input
            type="text"
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value)
              if (error) setError(null)
            }}
            onBlur={() => commitDraft(draft)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                commitDraft(draft)
              }
            }}
            className="gf-input w-full rounded-lg px-2 py-1.5 font-mono text-xs uppercase"
            spellCheck={false}
            aria-invalid={Boolean(error)}
          />
          {error ? (
            <span role="alert" className="mt-0.5 block text-[10px] text-rose-400">
              {error}
            </span>
          ) : (
            <span className="gf-page-muted mt-0.5 block text-[10px]">{hint}</span>
          )}
        </div>
      </div>
    </label>
  )
}
