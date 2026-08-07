import { useEffect, useRef, useState } from 'react'
import { Download, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'

type Props = {
  open: boolean
  title: string
  slug: string
  onClose: () => void
}

function buildPlayUrl(slug: string) {
  const origin = typeof window !== 'undefined' ? window.location.origin : 'https://gameforge.local'
  return `${origin}/play/${slug}`
}

function qrImageUrl(data: string) {
  return `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(data)}`
}

export function SharePosterModal({ open, title, slug, onClose }: Props) {
  const t = useT()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!open) {
      setReady(false)
      return
    }
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const playUrl = buildPlayUrl(slug)
    canvas.width = 600
    canvas.height = 840

    ctx.fillStyle = '#0a0a0a'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 36px system-ui, sans-serif'
    ctx.fillText('GameForge', 40, 70)

    ctx.font = '24px system-ui, sans-serif'
    wrapText(ctx, title, 40, 130, 520, 32)

    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      ctx.drawImage(img, 180, 280, 240, 240)
      ctx.fillStyle = 'rgba(255,255,255,0.55)'
      ctx.font = '14px monospace'
      ctx.fillText(playUrl, 40, 580)
      ctx.font = '16px system-ui, sans-serif'
      ctx.fillStyle = '#67e8f9'
      ctx.fillText(t('sharePosterScan'), 40, 620)
      setReady(true)
    }
    img.onerror = () => setReady(true)
    img.src = qrImageUrl(playUrl)
  }, [open, slug, title, t])

  function wrapText(
    context: CanvasRenderingContext2D,
    text: string,
    x: number,
    y: number,
    maxWidth: number,
    lineHeight: number,
  ) {
    const words = text.split(' ')
    let line = ''
    let cy = y
    for (const word of words) {
      const test = line ? `${line} ${word}` : word
      if (context.measureText(test).width > maxWidth && line) {
        context.fillText(line, x, cy)
        line = word
        cy += lineHeight
      } else {
        line = test
      }
    }
    if (line) context.fillText(line, x, cy)
  }

  function download() {
    const canvas = canvasRef.current
    if (!canvas) return
    const link = document.createElement('a')
    link.download = `${slug}-poster.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[120] grid place-items-center bg-black/65 p-4" role="dialog">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-white/15 bg-[#12151a] p-5 shadow-2xl">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-medium text-white">{t('sharePosterTitle')}</h2>
          <button
            type="button"
            aria-label={t('close')}
            onClick={onClose}
            className="grid h-9 w-9 cursor-pointer place-items-center rounded-lg text-white/50 hover:bg-white/10 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <canvas
          ref={canvasRef}
          className="mx-auto w-full max-w-[300px] rounded-xl border border-white/10"
          aria-label={t('sharePosterTitle')}
        />
        <Button
          type="button"
          disabled={!ready}
          onClick={download}
          className="w-full !rounded-xl !bg-white !text-black hover:!bg-white/90"
        >
          <Download className="h-4 w-4" />
          {t('sharePosterDownload')}
        </Button>
      </div>
    </div>
  )
}
