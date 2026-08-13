import { type CSSProperties, type ReactNode } from 'react'
import { Inbox, Loader2 } from 'lucide-react'
import { useT } from '@/i18n/use-t'
import { EmptyState } from './EmptyState'

/** 表头淡底：跟随 --gf-text 的极低透明度，浅/深主题都成立。 */
const headerBg: CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--gf-text) 3%, transparent)',
}

/**
 * 后台通用表格。token 驱动容器（gf-admin-card，亮色下白底 + 柔弥散阴影，
 * 暗色背景回退到 var(--gf-surface)）；表头小号大写；行 hover 由 CSS
 * （.gf-admin-table tbody tr:hover）处理。empty 支持传字符串或自定义 ReactNode。
 */
export function AdminTable({
  headers,
  rows,
  loading,
  empty,
}: {
  headers: string[]
  rows: ReactNode[]
  loading?: boolean
  /** 空状态：传字符串走默认 EmptyState（带图标 + 文案），或自定义节点 */
  empty: ReactNode
}) {
  const t = useT()
  const emptyNode = typeof empty === 'string' ? <EmptyState icon={Inbox} title={empty} /> : empty

  return (
    <div className="gf-admin-card gf-admin-table overflow-hidden rounded-2xl">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead
            style={headerBg}
            className="gf-page-muted border-b border-[var(--gf-border)] text-[11px] font-medium tracking-wider uppercase"
          >
            <tr>
              {headers.map((h) => (
                <th key={h} className="px-4 py-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-[var(--gf-text)]">
            {loading ? (
              <tr>
                <td colSpan={headers.length} className="px-4 py-12">
                  <div className="gf-page-muted flex items-center justify-center gap-2 text-sm">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {t('loading')}
                  </div>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={headers.length}>{emptyNode}</td>
              </tr>
            ) : (
              rows
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
