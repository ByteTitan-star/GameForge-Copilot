import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, MoreVertical } from 'lucide-react'
import { templatesApi, templateEmoji, type GameTemplate } from '@/api/templates'
import { cn } from '@/lib/cn'
import { useT } from '@/i18n/use-t'

type Props = {
  onSelect: (template: GameTemplate) => void
  selectedId?: string | null
  className?: string
  /** onboarding 等窄容器用更密网格，不做三行定高视口 */
  compact?: boolean
}

const CORE_TAGS = ['action', 'casual', 'puzzle', 'strategy', 'simulation'] as const

export function TemplatePicker({
  onSelect,
  selectedId,
  className,
  compact = false,
}: Props) {
  const t = useT()
  const [tag, setTag] = useState<string | null>(null)
  const [tagsOpen, setTagsOpen] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const scrollTimer = useRef<number | null>(null)

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

  const extraTags = useMemo(
    () => tags.filter((tg) => !(CORE_TAGS as readonly string[]).includes(tg)),
    [tags],
  )

  useEffect(() => {
    return () => {
      if (scrollTimer.current != null) window.clearTimeout(scrollTimer.current)
    }
  }, [])

  function onScroll() {
    const el = scrollRef.current
    if (!el) return
    el.classList.add('is-scrolling')
    if (scrollTimer.current != null) window.clearTimeout(scrollTimer.current)
    scrollTimer.current = window.setTimeout(() => {
      el.classList.remove('is-scrolling')
    }, 700)
  }

  return (
    <section className={cn('gf-inspire', className)}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-[15px] font-semibold tracking-[-0.015em] text-[var(--gf-text)]">
          {t('forgeInspireTitle')}
        </h2>
        {tags.length > 0 ? (
          <button
            type="button"
            aria-label={t('more')}
            aria-expanded={tagsOpen}
            onClick={() => setTagsOpen((v) => !v)}
            className="gf-interactive grid h-7 w-7 cursor-pointer place-items-center rounded-lg text-[var(--gf-text-muted)] opacity-55 transition hover:bg-black/[0.04] hover:opacity-100"
          >
            <MoreVertical className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {tagsOpen && tags.length > 0 ? (
        <div className="mb-3 flex flex-wrap gap-1">
          <button
            type="button"
            onClick={() => setTag(null)}
            className={cn(
              'cursor-pointer rounded-lg px-2.5 py-1 text-[12px] transition',
              tag === null
                ? 'bg-[rgba(var(--gf-primary-rgb),0.1)] font-semibold text-[var(--gf-primary)]'
                : 'text-[var(--gf-text-muted)] hover:bg-black/[0.04] hover:text-[var(--gf-text)]',
            )}
          >
            {t('filterAll')}
          </button>
          {CORE_TAGS.filter((tg) => tags.includes(tg)).map((tg) => (
            <button
              key={tg}
              type="button"
              onClick={() => setTag(tg)}
              className={cn(
                'cursor-pointer rounded-lg px-2.5 py-1 text-[12px] transition',
                tag === tg
                  ? 'bg-[rgba(var(--gf-primary-rgb),0.1)] font-semibold text-[var(--gf-primary)]'
                  : 'text-[var(--gf-text-muted)] hover:bg-black/[0.04] hover:text-[var(--gf-text)]',
              )}
            >
              {tg}
            </button>
          ))}
          {extraTags.map((tg) => (
            <button
              key={tg}
              type="button"
              onClick={() => setTag(tg)}
              className={cn(
                'cursor-pointer rounded-lg px-2.5 py-1 text-[12px] transition',
                tag === tg
                  ? 'bg-[rgba(var(--gf-primary-rgb),0.1)] font-semibold text-[var(--gf-primary)]'
                  : 'text-[var(--gf-text-muted)] hover:bg-black/[0.04] hover:text-[var(--gf-text)]',
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
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className={cn(
            compact
              ? 'max-h-[min(320px,50vh)] overflow-y-auto'
              : 'gf-inspire-scroll',
          )}
        >
          <div
            className={cn(
              'gf-inspire-grid grid gap-2.5',
              compact
                ? 'grid-cols-2'
                : 'grid-cols-3 sm:grid-cols-4 md:grid-cols-5 xl:grid-cols-6',
            )}
          >
            {filtered.map((tpl) => {
              const active = selectedId === tpl.template_id
              return (
                <button
                  key={tpl.template_id}
                  type="button"
                  title={tpl.title}
                  onClick={() => onSelect(tpl)}
                  className={cn(
                    'gf-inspire-card gf-interactive flex min-w-0 cursor-pointer flex-col overflow-hidden rounded-2xl text-left outline outline-1 transition',
                    active
                      ? 'bg-[rgba(var(--gf-primary-rgb),0.08)] outline-[rgba(var(--gf-primary-rgb),0.28)]'
                      : 'bg-white/70 outline-[rgba(15,23,42,0.06)] hover:bg-white hover:outline-[rgba(var(--gf-primary-rgb),0.22)] hover:shadow-[0_8px_20px_rgba(15,23,42,0.05)]',
                  )}
                >
                  <span className="gf-inspire-icon" aria-hidden>
                    {templateEmoji(tpl.template_id, tpl.tags)}
                  </span>
                  <span className="gf-inspire-title">{tpl.title}</span>
                  {tpl.description ? (
                    <span className="gf-inspire-desc">{tpl.description}</span>
                  ) : (
                    <span className="gf-inspire-desc" aria-hidden>
                      &nbsp;
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </section>
  )
}
