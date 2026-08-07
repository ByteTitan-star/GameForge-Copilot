import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { meApi } from '@/api/me'
import { pickDefaultLlmConfigId } from '@/lib/llm-config'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Props = {
  accessToken: string
  value: string | null
  onChange: (configId: string | null) => void
  disabled?: boolean
  className?: string
}

export function LlmConfigSelect({ accessToken, value, onChange, disabled, className }: Props) {
  const t = useT()
  const q = useQuery({
    queryKey: ['llm-configs', 'forge-select'],
    queryFn: () => meApi.listLlmConfigs(accessToken),
    enabled: Boolean(accessToken),
  })

  const configs = q.data ?? []
  const defaultId = pickDefaultLlmConfigId(configs)
  const selected = value ?? defaultId

  if (q.isLoading) {
    return <p className={cn('text-xs gf-page-muted', className)}>{t('loading')}</p>
  }

  if (configs.length === 0) {
    return (
      <div className={cn('text-xs', className)}>
        <span className="gf-page-muted">{t('llmConfigNone')}</span>{' '}
        <Link to="/settings" className="gf-text-accent underline-offset-2 hover:underline">
          {t('llmConfigGoSettings')}
        </Link>
      </div>
    )
  }

  return (
    <label className={cn('flex items-center gap-2 text-xs', className)}>
      <span className="shrink-0 gf-page-muted">{t('llmConfigSelect')}</span>
      <select
        value={selected ?? ''}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value || null)}
        className="gf-border-subtle min-w-0 flex-1 cursor-pointer rounded-lg border bg-black/[0.03] px-2 py-1.5 gf-page-body outline-none focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.35)] disabled:opacity-50"
      >
        {configs.map((c) => (
          <option key={c.config_id} value={c.config_id}>
            {c.provider} · {c.model}
            {c.is_default ? ` (${t('llmDefault')})` : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
