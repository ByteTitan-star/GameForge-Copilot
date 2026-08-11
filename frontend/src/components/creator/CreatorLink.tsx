import { Link } from 'react-router-dom'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

export type CreatorRef = {
  handle: string
  display_name?: string | null
}

type Props = {
  creator?: CreatorRef | null
  authorHandle?: string | null
  authorDisplay?: string | null
  official?: boolean
  variant?: 'dark' | 'theme'
  className?: string
}

export function CreatorLink({
  creator,
  authorHandle,
  authorDisplay,
  official = false,
  variant = 'dark',
  className,
}: Props) {
  const t = useT()
  const theme = variant === 'theme'

  if (official) {
    return (
      <span className={cn('text-xs', theme ? 'gf-page-muted' : 'text-white/50', className)}>
        {t('officialCreator')}
      </span>
    )
  }

  const handle = creator?.handle ?? authorHandle
  if (!handle) {
    if (authorDisplay) {
      return (
        <span className={cn('text-xs', theme ? 'gf-page-muted' : 'text-white/50', className)}>
          {authorDisplay}
        </span>
      )
    }
    return null
  }

  const label = creator?.display_name ?? authorDisplay ?? `@${handle}`
  return (
    <Link
      to={`/u/${handle}`}
      className={cn(
        'text-xs underline-offset-2 transition hover:underline',
        theme ? 'gf-text-accent' : 'text-cyan-200/85 hover:text-cyan-100',
        className,
      )}
    >
      {t('creatorBy').replace('{name}', label.startsWith('@') ? label : `@${handle}`)}
    </Link>
  )
}
