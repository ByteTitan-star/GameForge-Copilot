import { Link } from 'react-router-dom'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Loader2 } from 'lucide-react'
import { templatesApi, templateEmoji, type GameTemplate } from '@/api/templates'
import { cn } from '@/lib/cn'
import { useT } from '@/i18n/use-t'

type Props = {
  onSelect: (template: GameTemplate) => void
  selectedId?: string | null
  className?: string
  compact?: boolean
}

export function TemplatePicker({ onSelect, selectedId, className, compact = false }: Props) {
  const t = useT()
  const [tag, setTag] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['templates'],
    queryFn: () => templatesApi.list(),
  })

  const templates = q.data ?? []

  const tags = useMemo(() => {
    const set = new Set<string>()
    for (const tpl of templates) {
      for (const tg of tpl.tags) set.add(tg)
    }
    return [...set].sort()
  }, [templates])

  const filtered = useMemo(() => {
    if (!tag) return templates
    return templates.filter((tpl) => tpl.tags.includes(tag))
  }, [templates, tag])

  return (
    <section className={cn('space-y-3', className)}>
      <div>
        <p className="text-[11px] font-medium uppercase tracking-[0.12em] gf-page-muted">{t('templatePickerTitle')}</p>
        <p className="mt-1 text-sm gf-page-muted">{t('templatePickerSubtitle')}</p>
      </div>

      {tags.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setTag(null)}
            className={cn(
              'cursor-pointer rounded-full px-2.5 py-1 text-[11px] transition',
              tag === null ? 'gf-chip-active' : 'gf-chip hover:bg-black/[0.04]',
            )}
          >
            {t('filterAll')}
          </button>
          {tags.map((tg) => (
            <button
              key={tg}
              type="button"
              onClick={() => setTag(tg)}
              className={cn(
                'cursor-pointer rounded-full px-2.5 py-1 text-[11px] transition',
                tag === tg ? 'gf-chip-active' : 'gf-chip hover:bg-black/[0.04]',
              )}
            >
              {tg}
            </button>
          ))}
        </div>
      ) : null}

      {q.isLoading ? (
        <p className="gf-page-muted flex items-center gap-2 text-xs">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {t('loading')}
        </p>
      ) : (
        <div className={cn('grid gap-2', compact ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4')}>
          {filtered.map((tpl) => {
            const active = selectedId === tpl.template_id
            const playPath =
              tpl.playable && tpl.play_url
                ? `/play/template/${encodeURIComponent(tpl.template_id)}`
                : null
            return (
              <div
                key={tpl.template_id}
                className={cn(
                  'gf-interactive rounded-xl border p-3 transition',
                  active
                    ? 'gf-border-subtle border bg-[rgba(var(--gf-primary-rgb),0.1)] ring-1 ring-[rgba(var(--gf-primary-rgb),0.25)]'
                    : 'gf-border-subtle border bg-black/[0.02] hover:border-[rgba(var(--gf-primary-rgb),0.3)]',
                )}
              >
                <button
                  type="button"
                  onClick={() => onSelect(tpl)}
                  className="w-full cursor-pointer text-left"
                >
                  <span className="text-2xl" aria-hidden>
                    {templateEmoji(tpl.template_id, tpl.tags)}
                  </span>
                  <p className="mt-2 text-sm font-medium gf-page-body">{tpl.title}</p>
                  {tpl.description ? (
                    <p className="mt-1 line-clamp-2 text-[11px] gf-page-muted">{tpl.description}</p>
                  ) : null}
                </button>
                {playPath ? (
                  <Link
                    to={playPath}
                    onClick={(e) => e.stopPropagation()}
                    className="mt-2 inline-flex items-center gap-1 rounded-lg bg-[rgba(var(--gf-primary-rgb),0.12)] px-2 py-1 text-[11px] font-medium text-[rgb(var(--gf-primary-rgb))] transition hover:bg-[rgba(var(--gf-primary-rgb),0.18)]"
                  >
                    {t('officialPlay')}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                ) : (
                  <p className="mt-2 text-[10px] gf-page-muted">{t('templatePlaySoon')}</p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
