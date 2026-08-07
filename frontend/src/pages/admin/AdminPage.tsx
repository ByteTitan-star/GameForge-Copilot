import { useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Loader2, ShieldOff, X } from 'lucide-react'
import { adminApi } from '@/api/admin'
import { analyticsApi } from '@/api/analytics'
import { Role } from '@/api/enums'
import { formatApiError } from '@/api/error-message'
import type { PublishQueueItem } from '@/api/types'
import { Button } from '@/components/ui/button'
import { UsageChart } from '@/components/usage/UsageChart'
import { AnalyticsTrendChart } from '@/components/usage/UsageBreakdown'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { cn } from '@/lib/cn'

type Tab = 'queue' | 'published' | 'users' | 'usage' | 'analytics' | 'audit' | 'settings'

export function AdminPage() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const [tab, setTab] = useState<Tab>('queue')
  const [toast, setToast] = useState<string | null>(null)

  const tabs: { id: Tab; label: string }[] = [
    { id: 'queue', label: t('adminTabQueue') },
    { id: 'published', label: t('adminTabPublished') },
    { id: 'users', label: t('adminTabUsers') },
    { id: 'usage', label: t('adminTabUsage') },
    { id: 'analytics', label: t('adminTabAnalytics') },
    { id: 'audit', label: t('adminTabAudit') },
    { id: 'settings', label: t('adminTabSettings') },
  ]

  return (
    <div className="space-y-5">
      <div>
        <p className="font-mono text-[10px] tracking-[0.16em] text-white/35 uppercase">Admin</p>
        <h1 className="text-2xl tracking-tight text-white/95 md:text-3xl">{t('admin')}</h1>
        <p className="mt-1 text-sm text-white/40">{t('adminSubtitle')}</p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              'rounded-lg px-3 py-1.5 font-mono text-[11px] tracking-wide uppercase transition',
              tab === t.id
                ? 'bg-white text-black'
                : 'bg-white/[0.04] text-white/50 ring-1 ring-white/[0.06] hover:text-white/80',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {toast ? (
        <p role="status" className="rounded-lg border border-teal-400/20 bg-teal-400/10 px-3 py-2 text-sm text-teal-100">
          {toast}
        </p>
      ) : null}

      {tab === 'queue' && token ? <QueuePanel token={token} onToast={setToast} /> : null}
      {tab === 'published' && token ? <PublishedGamesPanel token={token} onToast={setToast} /> : null}
      {tab === 'users' && token ? <UsersPanel token={token} onToast={setToast} /> : null}
      {tab === 'usage' && token ? <UsagePanel token={token} /> : null}
      {tab === 'analytics' && token ? <AnalyticsPanel token={token} /> : null}
      {tab === 'audit' && token ? <AuditPanel token={token} /> : null}
      {tab === 'settings' && token ? <SettingsPanel token={token} onToast={setToast} /> : null}
    </div>
  )
}

function QueuePanel({
  token,
  onToast,
}: {
  token: string
  onToast: (m: string) => void
}) {
  const qc = useQueryClient()
  const [rejectId, setRejectId] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  const queue = useQuery({
    queryKey: ['admin', 'publish-queue'],
    queryFn: () => adminApi.listPublishQueue(token),
  })

  const pending = useMemo(
    () => (queue.data?.data ?? []).filter((x) => x.status === 'submitted' || x.status === 'reviewing'),
    [queue.data],
  )

  const approveMu = useMutation({
    mutationFn: (id: string) => adminApi.approvePublish(id, token),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'publish-queue'] })
      onToast('已通过并上架')
    },
    onError: (e) => onToast(formatApiError(e, '审批失败')),
  })

  const rejectMu = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminApi.rejectPublish(id, reason, token),
    onSuccess: async () => {
      setRejectId(null)
      setReason('')
      await qc.invalidateQueries({ queryKey: ['admin', 'publish-queue'] })
      onToast('已驳回')
    },
    onError: (e) => onToast(formatApiError(e, '驳回失败')),
  })

  return (
    <div className="space-y-4">
      <AdminTable
        headers={['游戏', '版本', '状态', '提交时间', '操作']}
        loading={queue.isLoading}
        empty="暂无待审单据"
        rows={pending.map((item) => (
          <QueueRow
            key={item.publish_request_id}
            item={item}
            busy={approveMu.isPending || rejectMu.isPending}
            onApprove={() => approveMu.mutate(item.publish_request_id)}
            onReject={() => {
              setRejectId(item.publish_request_id)
              setReason('')
            }}
          />
        ))}
      />

      {rejectId ? (
        <Modal
          title="驳回理由"
          onClose={() => setRejectId(null)}
          onConfirm={() => rejectMu.mutate({ id: rejectId, reason: reason.trim() })}
          confirmLabel="确认驳回"
          confirmDisabled={!reason.trim() || rejectMu.isPending}
        >
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none"
            placeholder="说明驳回原因…"
          />
        </Modal>
      ) : null}
    </div>
  )
}

function QueueRow({
  item,
  busy,
  onApprove,
  onReject,
}: {
  item: PublishQueueItem
  busy: boolean
  onApprove: () => void
  onReject: () => void
}) {
  return (
    <tr className="border-t border-white/[0.06]">
      <td className="px-4 py-3 text-white/85">{item.game_title}</td>
      <td className="px-4 py-3 font-mono text-xs text-white/50">v{item.version}</td>
      <td className="px-4 py-3 font-mono text-xs text-cyan-200/80">{item.status}</td>
      <td className="px-4 py-3 font-mono text-xs text-white/40">
        {new Date(item.created_at).toLocaleString()}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1.5">
          <Button
            className="!h-8 !rounded-lg !bg-teal-400 !px-2.5 !text-xs !text-black hover:!bg-teal-300"
            disabled={busy}
            onClick={onApprove}
          >
            <Check className="h-3.5 w-3.5" />
            通过
          </Button>
          <Button
            variant="ghost"
            className="!h-8 !rounded-lg !px-2.5 !text-xs !text-red-200/80 hover:!bg-red-400/10"
            disabled={busy}
            onClick={onReject}
          >
            <X className="h-3.5 w-3.5" />
            驳回
          </Button>
        </div>
      </td>
    </tr>
  )
}

function UsersPanel({ token, onToast }: { token: string; onToast: (m: string) => void }) {
  const qc = useQueryClient()
  const meId = useAuthStore((s) => s.user?.user_id)
  const [quotaDraft, setQuotaDraft] = useState<Record<string, string>>({})
  const [disableTarget, setDisableTarget] = useState<{ userId: string; email: string } | null>(
    null,
  )
  const [deleteTarget, setDeleteTarget] = useState<{ userId: string; email: string } | null>(null)
  const users = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => adminApi.listUsers(token),
  })
  const settings = useQuery({
    queryKey: ['admin', 'settings'],
    queryFn: () => adminApi.getSettings(token),
  })
  const contactEmail = settings.data?.admin_contact_email || '管理员'

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
    }) => adminApi.patchUser(userId, { role, disabled, daily_token_limit }, token),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'users'] })
      onToast('用户已更新')
    },
    onError: (e) => onToast(formatApiError(e, '更新失败')),
  })

  const deleteMu = useMutation({
    mutationFn: (userId: string) => adminApi.deleteUser(userId, token),
    onSuccess: async () => {
      setDeleteTarget(null)
      await qc.invalidateQueries({ queryKey: ['admin', 'users'] })
      onToast('用户已删除')
    },
    onError: (e) => onToast(formatApiError(e, '删除失败')),
  })

  return (
    <div className="space-y-4">
      <p className="text-sm text-white/45">
        禁用后用户无法登录，提示：当前账号已违规，请联系管理员&lt;{contactEmail}&gt;申请解封
      </p>
      <AdminTable
      headers={['邮箱', '角色', '验证', '状态', '日配额覆盖', '操作']}
      loading={users.isLoading}
      empty="暂无用户"
      rows={(users.data?.data ?? []).map((u) => (
        <tr key={u.user_id} className="border-t border-white/[0.06]">
          <td className="px-4 py-3 text-white/85">{u.email}</td>
          <td className="px-4 py-3 font-mono text-xs text-white/50">{u.role}</td>
          <td className="px-4 py-3 text-xs text-white/45">{u.email_verified ? '已验证' : '未验证'}</td>
          <td className="px-4 py-3 text-xs">
            <span className={u.disabled ? 'text-red-300/80' : 'text-teal-200/80'}>
              {u.disabled ? '禁用' : '正常'}
            </span>
          </td>
          <td className="px-4 py-3">
            <div className="flex min-w-[140px] items-center gap-1">
              {(() => {
                const current =
                  u.daily_token_limit != null ? String(u.daily_token_limit) : ''
                const draft = quotaDraft[u.user_id] ?? current
                const parsed = draft.trim() === '' ? null : Number(draft)
                const canApply =
                  parsed != null &&
                  Number.isFinite(parsed) &&
                  parsed >= 0 &&
                  parsed !== u.daily_token_limit
                return (
                  <>
              <input
                type="number"
                placeholder="默认"
                value={draft}
                onChange={(e) =>
                  setQuotaDraft((prev) => ({ ...prev, [u.user_id]: e.target.value }))
                }
                className="h-8 w-24 rounded-lg border border-white/10 bg-black/30 px-2 font-mono text-xs text-white outline-none"
              />
              <Button
                variant="ghost"
                className="!h-8 !rounded-lg !px-2 !text-[11px] !text-teal-200/80"
                disabled={patchMu.isPending || !canApply}
                onClick={() =>
                  patchMu.mutate({
                    userId: u.user_id,
                    daily_token_limit: parsed!,
                  })
                }
              >
                应用
              </Button>
                  </>
                )
              })()}
              <Button
                variant="ghost"
                className="!h-8 !rounded-lg !px-2 !text-[11px] !text-white/40"
                disabled={patchMu.isPending}
                title="清除用户覆盖，回退全局默认"
                onClick={() => {
                  patchMu.mutate({ userId: u.user_id, daily_token_limit: null })
                  setQuotaDraft((prev) => ({ ...prev, [u.user_id]: '' }))
                }}
              >
                清除
              </Button>
            </div>
          </td>
          <td className="px-4 py-3">
            <div className="flex flex-wrap gap-1.5">
              <Button
                variant="ghost"
                className="!h-8 !rounded-lg !px-2.5 !text-xs !text-white/55"
                disabled={patchMu.isPending || u.user_id === meId}
                title={u.user_id === meId ? '不能修改当前登录账号' : undefined}
                onClick={() =>
                  patchMu.mutate({
                    userId: u.user_id,
                    role: u.role === Role.admin ? Role.user : Role.admin,
                  })
                }
              >
                {u.role === Role.admin ? '降为普通用户' : '设为管理员'}
              </Button>
              <Button
                variant="ghost"
                className="!h-8 !rounded-lg !px-2.5 !text-xs !text-white/55"
                disabled={patchMu.isPending || u.user_id === meId}
                title={u.user_id === meId ? '不能禁用当前登录账号' : undefined}
                onClick={() =>
                  u.disabled
                    ? patchMu.mutate({ userId: u.user_id, disabled: false })
                    : setDisableTarget({ userId: u.user_id, email: u.email })
                }
              >
                {u.disabled ? '启用' : '禁用'}
              </Button>
              <Button
                variant="ghost"
                className="!h-8 !rounded-lg !px-2.5 !text-xs !text-red-200/80 hover:!bg-red-400/10"
                disabled={deleteMu.isPending || u.user_id === meId}
                title={u.user_id === meId ? '不能删除当前登录账号' : undefined}
                onClick={() => setDeleteTarget({ userId: u.user_id, email: u.email })}
              >
                删除
              </Button>
            </div>
          </td>
        </tr>
      ))}
    />
      {disableTarget ? (
        <Modal
          title="禁用用户"
          onClose={() => setDisableTarget(null)}
          onConfirm={() => {
            patchMu.mutate({ userId: disableTarget.userId, disabled: true })
            setDisableTarget(null)
          }}
          confirmLabel="确认禁用"
          confirmDisabled={patchMu.isPending}
          danger
        >
          <p className="text-sm text-white/70">
            确定禁用 <span className="text-white">{disableTarget.email}</span>？
          </p>
          <p className="mt-2 text-xs text-white/45">
            该用户将无法登录，并看到违规提示（联系 {contactEmail} 解封）。
          </p>
        </Modal>
      ) : null}
      {deleteTarget ? (
        <Modal
          title="删除用户"
          onClose={() => setDeleteTarget(null)}
          onConfirm={() => deleteMu.mutate(deleteTarget.userId)}
          confirmLabel="确认删除"
          confirmDisabled={deleteMu.isPending}
          danger
        >
          <p className="text-sm text-white/70">
            永久删除 <span className="text-white">{deleteTarget.email}</span>{' '}
            及其游戏、配置等数据，此操作不可恢复。
          </p>
        </Modal>
      ) : null}
    </div>
  )
}

function UsagePanel({ token }: { token: string }) {
  const usage = useQuery({
    queryKey: ['admin', 'usage'],
    queryFn: () => adminApi.usage(token),
  })
  const chart = useMemo(() => {
    const s = usage.data?.system
    if (!s) return []
    return [
      { name: '今日', input: s.today.input_tokens, output: s.today.output_tokens },
      { name: '本月', input: s.month.input_tokens, output: s.month.output_tokens },
      { name: '累计', input: s.total.input_tokens, output: s.total.output_tokens },
    ]
  }, [usage.data])

  if (usage.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-white/45">
        <Loader2 className="h-4 w-4 animate-spin" /> 加载用量…
      </div>
    )
  }

  return (
    <div className="space-y-4 rounded-2xl border border-white/[0.08] bg-[#12151a] p-5">
      <h2 className="text-lg text-white/90">系统用量</h2>
      <UsageChart data={chart} />
      <div>
        <p className="font-mono text-[10px] tracking-wider text-white/35 uppercase">Top users</p>
        <ul className="mt-2 space-y-1.5">
          {(usage.data?.top_users ?? []).map((u) => (
            <li
              key={u.user_id}
              className="flex justify-between rounded-xl bg-black/25 px-3 py-2 text-sm text-white/70 ring-1 ring-white/[0.04]"
            >
              <span>{u.email}</span>
              <span className="font-mono text-xs text-white/40">
                {u.month_input_tokens + u.month_output_tokens} tok · {u.calls} calls
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function PublishedGamesPanel({
  token,
  onToast,
}: {
  token: string
  onToast: (m: string) => void
}) {
  const qc = useQueryClient()
  const [takeDownGameId, setTakeDownGameId] = useState<string | null>(null)
  const [takeDownReason, setTakeDownReason] = useState('')

  const games = useQuery({
    queryKey: ['admin', 'games', 'published'],
    queryFn: () => adminApi.listGames(token, 'published'),
  })

  const featuredMu = useMutation({
    mutationFn: ({ gameId, featured }: { gameId: string; featured: boolean }) =>
      adminApi.setFeatured(gameId, featured, token),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'games', 'published'] })
      await qc.invalidateQueries({ queryKey: ['featured-games'] })
      onToast('精选状态已更新')
    },
    onError: (e) => onToast(formatApiError(e, '操作失败')),
  })

  const takeDownMu = useMutation({
    mutationFn: ({ gameId, reason }: { gameId: string; reason: string }) =>
      adminApi.takeDown(gameId, reason, token),
    onSuccess: async () => {
      setTakeDownGameId(null)
      setTakeDownReason('')
      await qc.invalidateQueries({ queryKey: ['admin', 'games', 'published'] })
      onToast('已下架')
    },
    onError: (e) => onToast(formatApiError(e, '下架失败')),
  })

  const rows = games.data?.data ?? []

  return (
    <div className="space-y-4">
      <AdminTable
        headers={['游戏', 'slug', '版本', '更新时间', '操作']}
        loading={games.isLoading}
        empty="暂无已发布游戏"
        rows={rows.map((g) => (
          <tr key={g.game_id} className="border-t border-white/[0.06]">
            <td className="px-4 py-3 text-white/85">{g.title}</td>
            <td className="px-4 py-3 font-mono text-xs text-cyan-200/80">{g.slug ?? '—'}</td>
            <td className="px-4 py-3 font-mono text-xs text-white/50">v{g.current_version}</td>
            <td className="px-4 py-3 font-mono text-xs text-white/40">
              {new Date(g.updated_at).toLocaleString()}
            </td>
            <td className="px-4 py-3">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="ghost"
                  className="!h-8 !rounded-lg !px-2.5 !text-xs !text-amber-200/90 hover:!bg-amber-400/10"
                  disabled={featuredMu.isPending}
                  onClick={() =>
                    featuredMu.mutate({
                      gameId: g.game_id,
                      featured: !(g as { featured?: boolean }).featured,
                    })
                  }
                >
                  {(g as { featured?: boolean }).featured ? '取消精选' : '设为精选'}
                </Button>
                <Button
                  variant="ghost"
                  className="!h-8 !rounded-lg !px-2.5 !text-xs !text-red-200/80 hover:!bg-red-400/10"
                  disabled={takeDownMu.isPending}
                  onClick={() => {
                    setTakeDownGameId(g.game_id)
                    setTakeDownReason('')
                  }}
                >
                  <ShieldOff className="h-3.5 w-3.5" />
                  下架
                </Button>
              </div>
            </td>
          </tr>
        ))}
      />
      {takeDownGameId ? (
        <Modal
          title="下架游戏"
          onClose={() => setTakeDownGameId(null)}
          onConfirm={() =>
            takeDownMu.mutate({ gameId: takeDownGameId, reason: takeDownReason.trim() })
          }
          confirmLabel="确认下架"
          confirmDisabled={!takeDownReason.trim() || takeDownMu.isPending}
          danger
        >
          <textarea
            value={takeDownReason}
            onChange={(e) => setTakeDownReason(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none"
            placeholder="下架原因…"
          />
        </Modal>
      ) : null}
    </div>
  )
}

function AnalyticsPanel({ token }: { token: string }) {
  const t = useT()
  const q = useQuery({
    queryKey: ['admin', 'analytics'],
    queryFn: () => analyticsApi.getTop(token),
  })

  const data = q.data

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg text-white/90">{t('adminAnalyticsTitle')}</h2>
        <p className="mt-1 text-sm text-white/40">{t('adminAnalyticsSubtitle')}</p>
      </div>
      {q.isLoading ? <p className="text-sm text-white/40">{t('loading')}</p> : null}
      {data ? (
        <>
          <AdminTable
            headers={[t('usageBreakdownGame'), 'slug', t('adminAnalyticsPv'), t('adminAnalyticsPlays')]}
            loading={false}
            empty={t('usageBreakdownEmpty')}
            rows={data.top_games.map((g) => (
              <tr key={g.game_id} className="border-t border-white/[0.06]">
                <td className="px-4 py-3 text-sm text-white/85">{g.title}</td>
                <td className="px-4 py-3 font-mono text-xs text-cyan-200/70">{g.slug}</td>
                <td className="px-4 py-3 font-mono text-sm text-teal-300">{g.page_views.toLocaleString()}</td>
                <td className="px-4 py-3 font-mono text-sm text-white/55">{g.play_count.toLocaleString()}</td>
              </tr>
            ))}
          />
          <section className="rounded-2xl border border-white/[0.08] bg-[#12151a] p-4">
            <p className="mb-3 font-mono text-[10px] tracking-wider text-white/40 uppercase">{t('adminAnalyticsTrend')}</p>
            <AnalyticsTrendChart data={data.trend} />
          </section>
        </>
      ) : null}
    </div>
  )
}

function AuditPanel({ token }: { token: string }) {
  const logs = useQuery({
    queryKey: ['admin', 'audit-logs'],
    queryFn: () => adminApi.listAuditLogs(token),
  })

  return (
    <AdminTable
      headers={['时间', '操作', '目标', '操作者']}
      loading={logs.isLoading}
      empty="暂无审计记录"
      rows={(logs.data?.data ?? []).map((row) => (
        <tr key={row.id} className="border-t border-white/[0.06]">
          <td className="px-4 py-3 font-mono text-xs text-white/40">
            {new Date(row.created_at).toLocaleString()}
          </td>
          <td className="px-4 py-3 font-mono text-xs text-cyan-200/80">{row.action}</td>
          <td className="px-4 py-3 font-mono text-xs text-white/55">{row.target ?? '—'}</td>
          <td className="px-4 py-3 font-mono text-xs text-white/45">{row.actor_id}</td>
        </tr>
      ))}
    />
  )
}

function SettingsPanel({ token, onToast }: { token: string; onToast: (m: string) => void }) {
  const qc = useQueryClient()
  const settings = useQuery({
    queryKey: ['admin', 'settings'],
    queryFn: () => adminApi.getSettings(token),
  })
  const [daily, setDaily] = useState<number | ''>('')
  const [monthly, setMonthly] = useState<number | ''>('')
  const [rate, setRate] = useState<number | ''>('')
  const [contactEmail, setContactEmail] = useState('')

  const loaded = settings.data
  const dailyVal = daily === '' ? (loaded?.default_daily_token_limit ?? '') : daily
  const monthlyVal = monthly === '' ? (loaded?.default_monthly_token_limit ?? '') : monthly
  const rateVal = rate === '' ? (loaded?.default_rate_limit_per_min ?? '') : rate
  const contactVal = contactEmail === '' ? (loaded?.admin_contact_email ?? '') : contactEmail

  const saveMu = useMutation({
    mutationFn: () =>
      adminApi.updateSettings(
        {
          default_daily_token_limit: Number(dailyVal),
          default_monthly_token_limit: Number(monthlyVal),
          default_rate_limit_per_min: Number(rateVal),
          admin_contact_email: String(contactVal).trim(),
        },
        token,
      ),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'settings'] })
      setDaily('')
      setMonthly('')
      setRate('')
      setContactEmail('')
      onToast('设置已保存')
    },
    onError: (e) => onToast(formatApiError(e, '保存失败')),
  })

  return (
    <section className="max-w-lg space-y-4 rounded-2xl border border-white/[0.08] bg-[#12151a] p-5">
      <h2 className="text-lg text-white/90">全局设置</h2>
      <label className="block space-y-1.5 text-sm">
        <span className="font-mono text-[10px] text-white/40 uppercase">日 Token 配额默认值</span>
        <input
          type="number"
          value={dailyVal}
          onChange={(e) => setDaily(e.target.value === '' ? '' : Number(e.target.value))}
          className="h-10 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-white outline-none"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-mono text-[10px] text-white/40 uppercase">月 Token 配额默认值</span>
        <input
          type="number"
          value={monthlyVal}
          onChange={(e) => setMonthly(e.target.value === '' ? '' : Number(e.target.value))}
          className="h-10 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-white outline-none"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-mono text-[10px] text-white/40 uppercase">每分钟限流</span>
        <input
          type="number"
          value={rateVal}
          onChange={(e) => setRate(e.target.value === '' ? '' : Number(e.target.value))}
          className="h-10 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-white outline-none"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="font-mono text-[10px] text-white/40 uppercase">管理员联系邮箱</span>
        <input
          type="email"
          value={contactVal}
          onChange={(e) => setContactEmail(e.target.value)}
          placeholder="wxcurry@163.com"
          className="h-10 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-white outline-none"
        />
        <p className="text-xs text-white/35">账号禁用时，登录页提示用户联系此邮箱申请解封。</p>
      </label>
      <Button
        className="!rounded-lg !bg-teal-400 !text-black hover:!bg-teal-300"
        disabled={saveMu.isPending || !dailyVal || !monthlyVal || !rateVal || !contactVal}
        onClick={() => saveMu.mutate()}
      >
        {saveMu.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        保存
      </Button>
    </section>
  )
}

function AdminTable({
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
  return (
    <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[#12151a]">
      <table className="w-full text-left text-sm">
        <thead className="bg-white/[0.03] font-mono text-[10px] tracking-wider text-white/40 uppercase">
          <tr>
            {headers.map((h) => (
              <th key={h} className="px-4 py-3">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="text-white/75">
          {loading ? (
            <tr>
              <td colSpan={headers.length} className="px-4 py-8 text-white/40">
                <Loader2 className="inline h-4 w-4 animate-spin" /> 加载中…
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={headers.length} className="px-4 py-8 text-white/35">
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

function Modal({
  title,
  children,
  onClose,
  onConfirm,
  confirmLabel,
  confirmDisabled,
  danger,
}: {
  title: string
  children: ReactNode
  onClose: () => void
  onConfirm: () => void
  confirmLabel: string
  confirmDisabled?: boolean
  danger?: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="dialog">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-white/10 bg-[#161a20] p-5 shadow-2xl">
        <h3 className="text-base text-white/90">{title}</h3>
        {children}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" className="!rounded-lg !text-white/55" onClick={onClose}>
            取消
          </Button>
          <Button
            className={cn(
              '!rounded-lg',
              danger
                ? '!bg-red-400 !text-black hover:!bg-red-300'
                : '!bg-teal-400 !text-black hover:!bg-teal-300',
            )}
            disabled={confirmDisabled}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
