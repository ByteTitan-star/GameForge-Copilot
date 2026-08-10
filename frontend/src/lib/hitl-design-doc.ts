export type ParsedDesignDoc = {
  title: string
  gameplay: string
  controls: string
  levels: string[]
}

export function parseDesignDoc(raw: unknown, fallbackTitle = ''): ParsedDesignDoc {
  if (typeof raw === 'string') {
    return { title: fallbackTitle, gameplay: raw, controls: '', levels: [] }
  }
  if (raw && typeof raw === 'object') {
    const o = raw as Record<string, unknown>
    const levelsRaw = o.levels
    let levels: string[] = []
    if (Array.isArray(levelsRaw)) {
      levels = levelsRaw.map((lv) => {
        if (typeof lv === 'string') return lv
        if (lv && typeof lv === 'object' && 'name' in lv) return String((lv as { name: unknown }).name)
        return JSON.stringify(lv)
      })
    }
    return {
      title: String(o.title ?? fallbackTitle),
      gameplay: String(o.gameplay ?? ''),
      controls: String(o.controls ?? ''),
      levels,
    }
  }
  return { title: fallbackTitle, gameplay: '', controls: '', levels: [] }
}
