import { type CSSProperties, type ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { useT } from '@/i18n/use-t'

/** 表头淡底：跟随 --gf-text 的极低透明度，浅/深主题都成立。 */
const headerBg: CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--gf-text) 3%, transparent)',
}

/**
 * 后台通用表格。token 驱动（gf-glass 容器 + var(--gf-text) 正文 + gf-page-muted 弱化），
 * 跟随全局主题，不硬编码颜色。
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
  empty: string
}) {
  const t = useT()
  return (
    <div className="gf-glass overflow-hidden rounded-2xl">
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
              <td colSpan={headers.length} className="gf-page-muted px-4 py-8">
                <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
                {t('loading')}
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={headers.length} className="gf-page-muted px-4 py-8">
                {empty}
              </td>
            </tr>
          ) : (
            rows
          )}
        </tbody>
      </table>
    </div>
  )
}
