import { type ComponentType, type ReactNode } from 'react'

/**
 * 后台空状态。取代旧表格里一行冷冰冰的「暂无数据」文字：
 * 带图标（复用 gf-empty-icon-wrap，token 驱动柔色块）+ 标题 + 可选描述 + 可选 CTA。
 * icon 传 lucide 组件类型（与 AdminTable 调用方约定）。
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: ComponentType<{ className?: string }>
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      {Icon ? (
        <span className="gf-empty-icon-wrap grid h-12 w-12 place-items-center rounded-2xl">
          <Icon className="gf-text-accent h-5 w-5" />
        </span>
      ) : null}
      <div className="space-y-1">
        <p className="gf-page-body text-sm font-medium">{title}</p>
        {description ? <p className="gf-page-muted text-xs">{description}</p> : null}
      </div>
      {action}
    </div>
  )
}
