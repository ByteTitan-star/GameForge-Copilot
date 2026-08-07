import { useEffect, useState } from 'react'
import { cn } from '@/lib/cn'

type Props = {
  src: string
  title?: string
  variant?: 'light' | 'console' | 'stage'
  className?: string
  /** 草稿托管需 Bearer；iframe 无法带头，内部改为 fetch→blob */
  accessToken?: string | null
}

function isDraftUrl(src: string): boolean {
  return /\/draft\//.test(src)
}

/** 试玩容器：sandbox 不含 allow-same-origin（对齐 docs/08） */
export function GamePlayer({
  src,
  title = 'Game preview',
  variant = 'light',
  className,
  accessToken,
}: Props) {
  const console = variant === 'console'
  const stage = variant === 'stage'
  const [iframeSrc, setIframeSrc] = useState(src)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let revoked: string | null = null
    let cancelled = false

    async function load() {
      setError(null)
      const needsAuthFetch = isDraftUrl(src) && Boolean(accessToken)
      if (!needsAuthFetch) {
        setIframeSrc(src)
        return
      }
      try {
        const res = await fetch(src, {
          headers: { Authorization: `Bearer ${accessToken}`, Accept: 'text/html' },
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const html = await res.text()
        const blobUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
        revoked = blobUrl
        if (!cancelled) setIframeSrc(blobUrl)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : '加载失败')
      }
    }

    void load()
    return () => {
      cancelled = true
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [src, accessToken])

  return (
    <div
      className={cn(
        'overflow-hidden',
        stage
          ? 'relative h-full w-full bg-black'
          : console
            ? 'h-full rounded-xl border border-white/[0.08] bg-black/40'
            : 'rounded-2xl border border-[rgba(30,50,90,0.1)] bg-white shadow-sm',
        className,
      )}
    >
      <div
        className={cn(
          'border-b px-4 py-2 text-xs',
          stage
            ? 'absolute left-4 top-4 z-10 rounded-lg border border-white/10 bg-black/45 px-3 py-1.5 font-mono text-[10px] tracking-[0.14em] text-white/60 uppercase backdrop-blur-md'
            : console
              ? 'border-white/[0.06] font-mono text-white/45'
              : 'border-[rgba(30,50,90,0.08)] text-[rgba(30,50,90,0.55)]',
        )}
      >
        {title}
      </div>
      {error ? (
        <p className="p-4 text-sm text-red-400" role="alert">
          {error}
        </p>
      ) : (
        <iframe
          title={title}
          src={iframeSrc}
          sandbox="allow-scripts"
          className={cn(
            'w-full bg-[#111]',
            stage ? 'h-full min-h-0' : console ? 'h-[calc(100%-2.25rem)] min-h-[280px]' : 'h-[70vh]',
          )}
        />
      )}
    </div>
  )
}
