import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldOff, Star } from 'lucide-react'
import { adminApi } from '@/api/admin'
import { formatApiError } from '@/api/error-message'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { AdminTable } from '@/components/admin/AdminTable'
import { ConfirmModal } from '@/components/admin/ConfirmModal'
import { btnDanger, btnNeutral } from '@/components/admin/buttonStyles'
import { useAdminToast } from '../adminToast'

export function PublishedSection() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const onToast = useAdminToast()
  const qc = useQueryClient()
  const [takeDownGameId, setTakeDownGameId] = useState<string | null>(null)
  const [takeDownReason, setTakeDownReason] = useState('')

  const games = useQuery({
    queryKey: ['admin', 'games', 'published'],
    queryFn: () => adminApi.listGames(token!, 'published'),
  })

  const featuredMu = useMutation({
    mutationFn: ({ gameId, featured }: { gameId: string; featured: boolean }) =>
      adminApi.setFeatured(gameId, featured, token!),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'games', 'published'] })
      await qc.invalidateQueries({ queryKey: ['featured-games'] })
      onToast(t('adminFeaturedOk'))
    },
    onError: (e) => onToast(formatApiError(e, t('adminOpFail'))),
  })

  const takeDownMu = useMutation({
    mutationFn: ({ gameId, reason }: { gameId: string; reason: string }) =>
      adminApi.takeDown(gameId, reason, token!),
    onSuccess: async () => {
      setTakeDownGameId(null)
      setTakeDownReason('')
      await qc.invalidateQueries({ queryKey: ['admin', 'games', 'published'] })
      onToast(t('adminTakeDownOk'))
    },
    onError: (e) => onToast(formatApiError(e, t('adminTakeDownFail'))),
  })

  if (!token) return null

  const rows = games.data?.data ?? []

  return (
    <div className="space-y-4">
      <AdminTable
        headers={[
          t('adminColGame'),
          t('adminColSlug'),
          t('adminColVersion'),
          t('adminColUpdateTime'),
          t('adminColAction'),
        ]}
        loading={games.isLoading}
        empty={t('adminPublishedEmpty')}
        rows={rows.map((g) => {
          const featured = g.featured
          return (
            <tr key={g.game_id} className="border-t border-[var(--gf-border)]">
              <td className="px-4 py-3">{g.title}</td>
              <td className="gf-text-accent px-4 py-3 font-mono text-xs">{g.slug ?? '—'}</td>
              <td className="gf-page-muted px-4 py-3 font-mono text-xs">v{g.current_version}</td>
              <td className="gf-page-muted px-4 py-3 font-mono text-xs">
                {new Date(g.updated_at).toLocaleString()}
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={btnNeutral}
                    disabled={featuredMu.isPending}
                    onClick={() => featuredMu.mutate({ gameId: g.game_id, featured: !featured })}
                  >
                    <Star className={featured ? 'h-3.5 w-3.5 fill-current' : 'h-3.5 w-3.5'} />
                    {featured ? t('adminUnsetFeatured') : t('adminSetFeatured')}
                  </button>
                  <button
                    type="button"
                    className={btnDanger}
                    disabled={takeDownMu.isPending}
                    onClick={() => {
                      setTakeDownGameId(g.game_id)
                      setTakeDownReason('')
                    }}
                  >
                    <ShieldOff className="h-3.5 w-3.5" />
                    {t('adminTakeDown')}
                  </button>
                </div>
              </td>
            </tr>
          )
        })}
      />

      {takeDownGameId ? (
        <ConfirmModal
          title={t('adminTakeDownTitle')}
          onClose={() => setTakeDownGameId(null)}
          onConfirm={() =>
            takeDownMu.mutate({ gameId: takeDownGameId, reason: takeDownReason.trim() })
          }
          confirmLabel={t('adminConfirmTakeDown')}
          confirmDisabled={!takeDownReason.trim() || takeDownMu.isPending}
          danger
        >
          <textarea
            value={takeDownReason}
            onChange={(e) => setTakeDownReason(e.target.value)}
            rows={3}
            className="gf-input w-full rounded-xl px-3 py-2 text-sm"
            placeholder={t('adminTakeDownReasonPh')}
          />
        </ConfirmModal>
      ) : null}
    </div>
  )
}
