import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { AdminTable } from '@/components/admin/AdminTable'

export function AuditSection() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)

  const logs = useQuery({
    queryKey: ['admin', 'audit-logs'],
    queryFn: () => adminApi.listAuditLogs(token!),
  })

  if (!token) return null

  return (
    <div className="space-y-5">
      <AdminTable
        headers={[t('adminColTime'), t('adminColAction'), t('adminColTarget'), t('adminColActor')]}
        loading={logs.isLoading}
        empty={t('adminAuditEmpty')}
        rows={(logs.data?.data ?? []).map((row) => (
          <tr key={row.id} className="border-t border-[var(--gf-border)]">
            <td className="gf-page-muted px-4 py-3 font-mono text-xs">
              {new Date(row.created_at).toLocaleString()}
            </td>
            <td className="gf-text-accent px-4 py-3 font-mono text-xs">{row.action}</td>
            <td className="px-4 py-3 font-mono text-xs">{row.target ?? '—'}</td>
            <td className="gf-page-muted px-4 py-3 font-mono text-xs">{row.actor_id}</td>
          </tr>
        ))}
      />
    </div>
  )
}
