import { type ReactNode } from 'react'

/**
 * 后台 section 统一页头。token 驱动排版（gf-page-title / gf-page-subtitle），
 * 不引入新颜色。actions 槽留给后续顶部操作（刷新、导出等）。
 */
export function AdminPageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="gf-page-title leading-tight">{title}</h1>
        {subtitle ? <p className="gf-page-subtitle mt-1">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  )
}
