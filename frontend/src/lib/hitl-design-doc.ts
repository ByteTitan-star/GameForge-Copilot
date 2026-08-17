export type ParsedDesignDoc = {
  title: string
  gameplay: string
  controls: string
  levels: string[]
}

function asTextList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item) => {
      if (typeof item === 'string' && item.trim()) return [item]
      if (item && typeof item === 'object' && 'name' in item) {
        return [String((item as { name: unknown }).name)]
      }
      return []
    })
  }
  if (typeof value === 'string' && value.trim()) return [value]
  return []
}

export function parseDesignDoc(raw: unknown, fallbackTitle = ''): ParsedDesignDoc {
  if (typeof raw === 'string') {
    return { title: fallbackTitle, gameplay: raw, controls: '', levels: [] }
  }
  if (raw && typeof raw === 'object') {
    const o = raw as Record<string, unknown>
    return {
      title: String(o.title ?? fallbackTitle),
      gameplay: String(o.gameplay ?? ''),
      controls: asTextList(o.controls).join('\n'),
      levels: asTextList(o.levels),
    }
  }
  return { title: fallbackTitle, gameplay: '', controls: '', levels: [] }
}

export function designDocToMarkdown(raw: unknown, fallbackTitle = ''): string {
  if (typeof raw === 'string') return raw.trim() || `# ${fallbackTitle || '未命名游戏'}`
  if (!raw || typeof raw !== 'object') return `# ${fallbackTitle || '未命名游戏'}`
  const o = raw as Record<string, unknown>
  const lines: string[] = [`# ${String(o.title ?? fallbackTitle) || '未命名游戏'}`, '']
  const gameplay = String(o.gameplay ?? '').trim()
  if (gameplay) lines.push('## 玩法概述', gameplay, '')
  const controls = asTextList(o.controls)
  if (controls.length) {
    lines.push('## 操作控制', ...controls.map((item) => `- ${item}`), '')
  }
  const levels = asTextList(o.levels)
  if (levels.length) lines.push('## 关卡', ...levels.map((item) => `- ${item}`), '')
  const loop = asTextList(o.core_loop)
  if (loop.length) {
    lines.push('## 核心循环', ...loop.map((item, idx) => `${idx + 1}. ${item}`))
  }
  return lines.join('\n').trim()
}
