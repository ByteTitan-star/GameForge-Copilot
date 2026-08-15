import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { templatesApi } from '@/api/templates'
import { GamePlayer } from '@/components/game/GamePlayer'
import { templatePlayUrl } from '@/lib/hosting'
import { useT } from '@/i18n/use-t'

/** 模板 reference 产物试玩页（catalog.json reference_artifact）。 */
export function TemplatePlayPage() {
  const t = useT()
  const { templateId = '' } = useParams()
  const src = templatePlayUrl(templateId)

  const metaQ = useQuery({
    queryKey: ['template-play', templateId],
    enabled: Boolean(templateId),
    queryFn: () => templatesApi.list(),
  })

  const tpl = metaQ.data?.find((row) => row.template_id === templateId)
  const title = tpl?.title ?? templateId

  return (
    <div className="flex h-[100svh] flex-col bg-[#0a0a0a] text-white pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)]">
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-6 sm:px-6 md:py-8">
        <header className="mb-6 flex shrink-0 items-center gap-3">
          <Link
            to="/forge"
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 px-3 py-2 text-xs text-white/80 transition hover:border-white/30"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {t('forge')}
          </Link>
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/45">
              {t('templatePlayBadge')}
            </p>
            <h1 className="text-lg font-medium">{title}</h1>
          </div>
        </header>
        <section className="relative min-h-0 flex-1 overflow-hidden rounded-2xl border border-white/10 bg-black">
          <GamePlayer src={src} title={title} variant="stage" className="h-full" />
        </section>
      </div>
    </div>
  )
}
