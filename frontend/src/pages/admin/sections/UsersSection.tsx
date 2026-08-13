import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { Role } from '@/api/enums'
import { formatApiError } from '@/api/error-message'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { AdminTable } from '@/components/admin/AdminTable'
import { ConfirmModal } from '@/components/admin/ConfirmModal'
import { btnDanger, btnNeutral, btnPrimary } from '@/components/admin/buttonStyles'
import { useAdminToast } from '../adminToast'

export function UsersSection() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const onToast = useAdminToast()
  const qc = useQueryClient()
  const meId = useAuthStore((s) => s.user?.user_id)
  const [quotaDraft, setQuotaDraft] = useState<Record<string, string>>({})
  const [disableTarget, setDisableTarget] = useState<{ userId: string; email: string } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{ userId: string; email: string } | null>(null)

  const users = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => adminApi.listUsers(token!),
  })
  const settings = useQuery({
    queryKey: ['admin', 'settings'],
    queryFn: () => adminApi.getSettings(token!),
  })
  const contactEmail = settings.data?.admin_contact_email || t('adminContactFallback')

  const patchMu = useMutation({
    mutationFn: ({
      userId,
      role,
      disabled,
      daily_token_limit,
    }: {
      userId: string
      role?: 'user' | 'admin'
      disabled?: boolean
      daily_token_limit?: number | null
    }) => adminApi.patchUser(userId, { role, disabled, daily_token_limit }, token!),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'users'] })
      onToast(t('adminUserUpdated'))
    },
    onError: (e) => onToast(formatApiError(e, t('adminUpdateFail'))),
  })

  const deleteMu = useMutation({
    mutationFn: (userId: string) => adminApi.deleteUser(userId, token!),
    onSuccess: async () => {
      setDeleteTarget(null)
      await qc.invalidateQueries({ queryKey: ['admin', 'users'] })
      onToast(t('adminUserDeleted'))
    },
    onError: (e) => onToast(formatApiError(e, t('adminDeleteFail'))),
  })

  if (!token) return null

  return (
    <div className="space-y-5">
      <p className="gf-page-muted text-sm">
        {t('adminDisableBanner').replace('{email}', contactEmail)}
      </p>
      <AdminTable
        headers={[
          t('adminColEmail'),
          t('adminColRole'),
          t('adminColStatus'),
          t('adminColQuotaOverride'),
          t('adminColAction'),
        ]}
        loading={users.isLoading}
        empty={t('adminUsersEmpty')}
        rows={(users.data?.data ?? []).map((u) => {
          const current = u.daily_token_limit != null ? String(u.daily_token_limit) : ''
          const draft = quotaDraft[u.user_id] ?? current
          const parsed = draft.trim() === '' ? null : Number(draft)
          const canApply =
            parsed != null && Number.isFinite(parsed) && parsed >= 0 && parsed !== u.daily_token_limit
          return (
            <tr key={u.user_id} className="group border-t border-[var(--gf-border)]">
              <td className="px-4 py-3">{u.email}</td>
              <td className="gf-page-muted px-4 py-3 font-mono text-xs">{u.role}</td>
              <td className="px-4 py-3 text-xs">
                <span
                  className={
                    u.disabled
                      ? 'inline-flex items-center rounded-full bg-rose-500/10 px-2 py-0.5 font-medium text-rose-700 ring-1 ring-inset ring-rose-500/20'
                      : 'inline-flex items-center rounded-full bg-emerald-500/10 px-2 py-0.5 font-medium text-emerald-700 ring-1 ring-inset ring-emerald-500/20'
                  }
                >
                  {u.disabled ? t('adminStatusDisabled') : t('adminStatusActive')}
                </span>
              </td>
              <td className="px-4 py-3">
                <div className="flex min-w-[140px] items-center gap-1">
                  <input
                    type="number"
                    placeholder={t('adminQuotaDefaultPh')}
                    value={draft}
                    onChange={(e) =>
                      setQuotaDraft((prev) => ({ ...prev, [u.user_id]: e.target.value }))
                    }
                    className="gf-input h-8 w-24 rounded-lg px-2 font-mono text-xs"
                  />
                  <button
                    type="button"
                    className={btnPrimary}
                    disabled={patchMu.isPending || !canApply}
                    onClick={() =>
                      patchMu.mutate({ userId: u.user_id, daily_token_limit: parsed })
                    }
                  >
                    {t('adminApply')}
                  </button>
                  <button
                    type="button"
                    className={btnNeutral}
                    disabled={patchMu.isPending}
                    title={t('adminClearOverrideTitle')}
                    onClick={() => {
                      patchMu.mutate({ userId: u.user_id, daily_token_limit: null })
                      setQuotaDraft((prev) => ({ ...prev, [u.user_id]: '' }))
                    }}
                  >
                    {t('adminClearOverride')}
                  </button>
                </div>
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    className={btnNeutral}
                    disabled={patchMu.isPending || u.user_id === meId}
                    title={u.user_id === meId ? t('adminCannotEditSelf') : undefined}
                    onClick={() =>
                      patchMu.mutate({
                        userId: u.user_id,
                        role: u.role === Role.admin ? Role.user : Role.admin,
                      })
                    }
                  >
                    {u.role === Role.admin ? t('adminDemoteUser') : t('adminPromoteAdmin')}
                  </button>
                  <button
                    type="button"
                    className={btnNeutral}
                    disabled={patchMu.isPending || u.user_id === meId}
                    title={u.user_id === meId ? t('adminCannotDisableSelf') : undefined}
                    onClick={() =>
                      u.disabled
                        ? patchMu.mutate({ userId: u.user_id, disabled: false })
                        : setDisableTarget({ userId: u.user_id, email: u.email })
                    }
                  >
                    {u.disabled ? t('adminEnable') : t('adminDisable')}
                  </button>
                  <button
                    type="button"
                    className={btnDanger}
                    disabled={deleteMu.isPending || u.user_id === meId}
                    title={u.user_id === meId ? t('adminCannotDeleteSelf') : undefined}
                    onClick={() => setDeleteTarget({ userId: u.user_id, email: u.email })}
                  >
                    {t('adminDelete')}
                  </button>
                </div>
              </td>
            </tr>
          )
        })}
      />

      {disableTarget ? (
        <ConfirmModal
          title={t('adminDisableUserTitle')}
          onClose={() => setDisableTarget(null)}
          onConfirm={() => {
            patchMu.mutate({ userId: disableTarget.userId, disabled: true })
            setDisableTarget(null)
          }}
          confirmLabel={t('adminConfirmDisable')}
          confirmDisabled={patchMu.isPending}
          danger
        >
          <p className="text-sm text-[var(--gf-text)]">
            {t('adminDisableConfirm').replace('{email}', disableTarget.email)}
          </p>
          <p className="gf-page-muted mt-2 text-xs">
            {t('adminDisableBody').replace('{email}', contactEmail)}
          </p>
        </ConfirmModal>
      ) : null}

      {deleteTarget ? (
        <ConfirmModal
          title={t('adminDeleteUserTitle')}
          onClose={() => setDeleteTarget(null)}
          onConfirm={() => deleteMu.mutate(deleteTarget.userId)}
          confirmLabel={t('adminConfirmDelete')}
          confirmDisabled={deleteMu.isPending}
          danger
        >
          <p className="text-sm text-[var(--gf-text)]">
            {t('adminDeleteBody').replace('{email}', deleteTarget.email)}
          </p>
        </ConfirmModal>
      ) : null}
    </div>
  )
}
