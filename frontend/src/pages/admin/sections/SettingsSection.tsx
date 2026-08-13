import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { adminApi } from '@/api/admin'
import { formatApiError } from '@/api/error-message'
import { useAuthStore } from '@/stores/auth-store'
import { useT } from '@/i18n/use-t'
import { useAdminToast } from '../adminToast'

export function SettingsSection() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const onToast = useAdminToast()
  const qc = useQueryClient()
  const settings = useQuery({
    queryKey: ['admin', 'settings'],
    queryFn: () => adminApi.getSettings(token!),
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
        token!,
      ),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'settings'] })
      setDaily('')
      setMonthly('')
      setRate('')
      setContactEmail('')
      onToast(t('adminSettingsSaved'))
    },
    onError: (e) => onToast(formatApiError(e, t('adminSettingsSaveFail'))),
  })

  if (!token) return null

  return (
    <div className="space-y-5">
      <section className="gf-admin-card max-w-lg space-y-4 rounded-xl p-5">
        <label className="block space-y-1.5 text-sm">
        <span className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
          {t('adminDailyQuotaLabel')}
        </span>
        <input
          type="number"
          value={dailyVal}
          onChange={(e) => setDaily(e.target.value === '' ? '' : Number(e.target.value))}
          className="gf-input h-10 w-full rounded-xl px-3"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
          {t('adminMonthlyQuotaLabel')}
        </span>
        <input
          type="number"
          value={monthlyVal}
          onChange={(e) => setMonthly(e.target.value === '' ? '' : Number(e.target.value))}
          className="gf-input h-10 w-full rounded-xl px-3"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
          {t('adminRateLimitLabel')}
        </span>
        <input
          type="number"
          value={rateVal}
          onChange={(e) => setRate(e.target.value === '' ? '' : Number(e.target.value))}
          className="gf-input h-10 w-full rounded-xl px-3"
        />
      </label>
      <label className="block space-y-1.5 text-sm">
        <span className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
          {t('adminContactLabel')}
        </span>
        <input
          type="email"
          value={contactVal}
          onChange={(e) => setContactEmail(e.target.value)}
          placeholder="wxcurry@163.com"
          className="gf-input h-10 w-full rounded-xl px-3"
        />
        <p className="gf-page-muted text-xs">{t('adminContactHint')}</p>
      </label>
      <button
        type="button"
        className="gf-interactive gf-btn-primary inline-flex h-10 cursor-pointer items-center justify-center gap-2 px-5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
        disabled={saveMu.isPending || !dailyVal || !monthlyVal || !rateVal || !contactVal}
        onClick={() => saveMu.mutate()}
      >
        {saveMu.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {t('save')}
      </button>
      </section>
    </div>
  )
}
