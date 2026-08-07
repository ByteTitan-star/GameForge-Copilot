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
  className?: string
}

export function CreatorLink({
  creator,
  authorHandle,
  authorDisplay,
  official = false,
  className,
}: Props) {
  const t = useT()

  if (official) {
    return (
      <span className={cn('text-xs text-white/50', className)}>{t('officialCreator')}</span>
    )
  }

  const handle = creator?.handle ?? authorHandle
  if (!handle) {
    if (authorDisplay) {
      return <span className={cn('text-xs text-white/50', className)}>{authorDisplay}</span>
    }
    return null
  }

  const label = creator?.display_name ?? authorDisplay ?? `@${handle}`
  return (
    <Link
      to={`/u/${handle}`}
      className={cn(
        'text-xs text-cyan-200/85 underline-offset-2 transition hover:text-cyan-100 hover:underline',
        className,
      )}
    >
      {t('creatorBy').replace('{name}', label.startsWith('@') ? label : `@${handle}`)}
    </Link>
  )
}
