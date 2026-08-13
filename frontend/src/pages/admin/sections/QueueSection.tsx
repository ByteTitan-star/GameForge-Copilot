import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import { adminApi } from '@/api/admin'
import { formatApiError } from '@/api/error-message'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { AdminTable } from '@/components/admin/AdminTable'
import { ConfirmModal } from '@/components/admin/ConfirmModal'
import { btnDanger, btnPrimary } from '@/components/admin/buttonStyles'
import { useAdminToast } from '../adminToast'

export function QueueSection() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const onToast = useAdminToast()
  const qc = useQueryClient()
  const [rejectId, setRejectId] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  const queue = useQuery({
    queryKey: ['admin', 'publish-queue'],
    queryFn: () => adminApi.listPublishQueue(token!),
  })

  const pending = useMemo(
    () =>
      (queue.data?.data ?? []).filter(
        (x) => x.status === 'submitted' || x.status === 'reviewing',
      ),
    [queue.data],
  )

  const approveMu = useMutation({
    mutationFn: (id: string) => adminApi.approvePublish(id, token!),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'publish-queue'] })
      onToast(t('adminApproveOk'))
    },
    onError: (e) => onToast(formatApiError(e, t('adminApproveFail'))),
  })

  const rejectMu = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminApi.rejectPublish(id, reason, token!),
    onSuccess: async () => {
      setRejectId(null)
      setReason('')
      await qc.invalidateQueries({ queryKey: ['admin', 'publish-queue'] })
      onToast(t('adminRejectOk'))
    },
    onError: (e) => onToast(formatApiError(e, t('adminRejectFail'))),
  })

  if (!token) return null

  return (
    <div className="space-y-5">
      <AdminTable
        headers={[
          t('adminColGame'),
          t('adminColVersion'),
          t('adminColStatus'),
          t('adminColSubmitTime'),
          t('adminColAction'),
        ]}
        loading={queue.isLoading}
        empty={t('adminQueueEmpty')}
        rows={pending.map((item) => (
          <tr key={item.publish_request_id} className="group border-t border-[var(--gf-border)]">
            <td className="px-4 py-3">{item.game_title}</td>
            <td className="gf-page-muted px-4 py-3 font-mono text-xs">v{item.version}</td>
            <td className="gf-text-accent px-4 py-3 font-mono text-xs">{item.status}</td>
            <td className="gf-page-muted px-4 py-3 font-mono text-xs">
              {new Date(item.created_at).toLocaleString()}
            </td>
            <td className="px-4 py-3">
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  className={btnPrimary}
                  disabled={approveMu.isPending || rejectMu.isPending}
                  onClick={() => approveMu.mutate(item.publish_request_id)}
                >
                  <Check className="h-3.5 w-3.5" />
                  {t('adminApprove')}
                </button>
                <button
                  type="button"
                  className={btnDanger}
                  disabled={approveMu.isPending || rejectMu.isPending}
                  onClick={() => {
                    setRejectId(item.publish_request_id)
                    setReason('')
                  }}
                >
                  <X className="h-3.5 w-3.5" />
                  {t('adminReject')}
                </button>
              </div>
            </td>
          </tr>
        ))}
      />

      {rejectId ? (
        <ConfirmModal
          title={t('adminRejectReason')}
          onClose={() => setRejectId(null)}
          onConfirm={() => rejectMu.mutate({ id: rejectId, reason: reason.trim() })}
          confirmLabel={t('adminConfirmReject')}
          confirmDisabled={!reason.trim() || rejectMu.isPending}
          danger
        >
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="gf-input w-full rounded-xl px-3 py-2 text-sm"
            placeholder={t('adminRejectReasonPh')}
          />
        </ConfirmModal>
      ) : null}
    </div>
  )
}
