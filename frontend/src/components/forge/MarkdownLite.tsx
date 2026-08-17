import type { ReactNode } from 'react'

function renderInline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

export function MarkdownLite({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const nodes: ReactNode[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i += 1
      continue
    }
    if (line.startsWith('# ')) {
      nodes.push(
        <h3 key={i} className="mt-1 text-[15px] font-semibold leading-snug">
          {renderInline(line.slice(2))}
        </h3>,
      )
      i += 1
      continue
    }
    if (line.startsWith('## ')) {
      nodes.push(
        <h4 key={i} className="mt-2 text-[13px] font-semibold leading-snug">
          {renderInline(line.slice(3))}
        </h4>,
      )
      i += 1
      continue
    }
    if (line.startsWith('- ')) {
      const items: string[] = []
      while (i < lines.length && lines[i].startsWith('- ')) {
        items.push(lines[i].slice(2))
        i += 1
      }
      nodes.push(
        <ul key={`ul-${i}`} className="mt-1 list-disc space-y-0.5 pl-4">
          {items.map((item, idx) => (
            <li key={idx}>{renderInline(item)}</li>
          ))}
        </ul>,
      )
      continue
    }
    if (/^\d+\.\s/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s/, ''))
        i += 1
      }
      nodes.push(
        <ol key={`ol-${i}`} className="mt-1 list-decimal space-y-0.5 pl-4">
          {items.map((item, idx) => (
            <li key={idx}>{renderInline(item)}</li>
          ))}
        </ol>,
      )
      continue
    }
    nodes.push(
      <p key={i} className="mt-1 leading-relaxed">
        {renderInline(line)}
      </p>,
    )
    i += 1
  }
  return <div className="text-[13px] gf-page-body">{nodes}</div>
}
