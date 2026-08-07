export type ParsedDesignDoc = {
  title: string
  gameplay: string
  controls: string
  levels: string[]
}

export type HitlFailureExtra = {
  error?: string
  errors: string[]
  retries?: number
  issues: string[]
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

export function parseHitlFailure(payload: Record<string, unknown>): HitlFailureExtra {
  const errors: string[] = []
  if (typeof payload.error === 'string' && payload.error) errors.push(payload.error)
  if (Array.isArray(payload.errors)) {
    for (const e of payload.errors) {
      if (typeof e === 'string' && e) errors.push(e)
    }
  }
  const issues: string[] = []
  if (Array.isArray(payload.issues)) {
    for (const i of payload.issues) {
      if (typeof i === 'string' && i) issues.push(i)
    }
  }
  return {
    error: typeof payload.error === 'string' ? payload.error : undefined,
    errors,
    retries: typeof payload.retries === 'number' ? payload.retries : undefined,
    issues,
  }
}

export function isFailureHitlNode(node: string): boolean {
  return node === 'sandbox_failed' || node === 'qa_failed'
}
