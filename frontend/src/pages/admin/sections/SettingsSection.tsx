import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { adminApi } from '@/api/admin'
import { formatApiError } from '@/api/error-message'
import { LLMProvider } from '@/api/enums'
import { ConfirmModal } from '@/components/admin/ConfirmModal'
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
  // 审核模型（护栏）：本地空串 = 未编辑，回显 loaded 值；apikey 回显 masked，留空=不改
  const [auditEnabled, setAuditEnabled] = useState<boolean | ''>('')
  const [auditProvider, setAuditProvider] = useState('')
  const [auditModel, setAuditModel] = useState('')
  const [auditApikey, setAuditApikey] = useState('')
  const [auditBaseUrl, setAuditBaseUrl] = useState('')
  const [disableAuditConfirmOpen, setDisableAuditConfirmOpen] = useState(false)

  const loaded = settings.data
  const dailyVal = daily === '' ? (loaded?.default_daily_token_limit ?? '') : daily
  const monthlyVal = monthly === '' ? (loaded?.default_monthly_token_limit ?? '') : monthly
  const rateVal = rate === '' ? (loaded?.default_rate_limit_per_min ?? '') : rate
  const contactVal = contactEmail === '' ? (loaded?.admin_contact_email ?? '') : contactEmail
  const auditLoaded = loaded?.audit_llm
  const auditEnabledVal = auditEnabled === '' ? (auditLoaded?.enabled ?? true) : auditEnabled
  const auditProviderVal = auditProvider || auditLoaded?.provider || LLMProvider.openai_compat
  const auditModelVal = auditModel || auditLoaded?.model || ''
  const auditApikeyVal = auditApikey || auditLoaded?.apikey || ''
  const auditBaseUrlVal = auditBaseUrl || auditLoaded?.base_url || ''

  const handleAuditEnabledChange = (checked: boolean) => {
    if (!checked && auditEnabledVal) {
      setDisableAuditConfirmOpen(true)
      return
    }
    setAuditEnabled(checked)
  }

  const saveMu = useMutation({
    mutationFn: () =>
      adminApi.updateSettings(
        {
          default_daily_token_limit: Number(dailyVal),
          default_monthly_token_limit: Number(monthlyVal),
          default_rate_limit_per_min: Number(rateVal),
          admin_contact_email: String(contactVal).trim(),
          audit_llm: {
            enabled: auditEnabledVal,
            provider: auditProviderVal,
            model: auditModelVal.trim(),
            // masked 形态原样回传 → 后端保留旧密钥；空串同理
            apikey: auditApikey.trim() ? auditApikeyVal : '',
            base_url: auditBaseUrlVal.trim(),
          },
        },
        token!,
      ),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['admin', 'settings'] })
      setDaily('')
      setMonthly('')
      setRate('')
      setContactEmail('')
      setAuditEnabled('')
      setAuditProvider('')
      setAuditModel('')
      setAuditApikey('')
      setAuditBaseUrl('')
      onToast(t('adminSettingsSaved'))
    },
    onError: (e) => onToast(formatApiError(e, t('adminSettingsSaveFail')), 'error'),
  })

  // 审核模型连通测试：用表单当前值 dry-test，不落库（照抄 LlmConfigPanel dryTestMu 模式）
  const auditTestMu = useMutation({
    mutationFn: () =>
      adminApi.testAuditLlm(
        {
          enabled: auditEnabledVal,
          provider: auditProviderVal,
          model: auditModelVal.trim(),
          apikey: auditApikey.trim() ? auditApikeyVal : '',
          base_url: auditBaseUrlVal.trim(),
        },
        token!,
      ),
    onSuccess: (r) =>
      r.tested_ok
        ? onToast(t('auditLlmTestOk'))
        : onToast(r.error ?? t('auditLlmTestFail'), 'error'),
    onError: (e) => onToast(formatApiError(e, t('auditLlmTestFailed')), 'error'),
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
          placeholder={t('adminContactPh')}
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

      <section className="gf-admin-card max-w-lg space-y-4 rounded-xl p-5">
        <div>
          <h3 className="gf-page-body text-sm font-semibold">{t('auditLlmTitle')}</h3>
          <p className="mt-1 gf-page-muted text-xs">{t('auditLlmHint')}</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={auditEnabledVal}
            onChange={(e) => handleAuditEnabledChange(e.target.checked)}
            className="h-4 w-4"
          />
          {t('auditLlmEnabled')}
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
            {t('auditLlmProvider')}
          </span>
          <select
            value={auditProviderVal}
            onChange={(e) => setAuditProvider(e.target.value)}
            className="gf-input h-10 w-full rounded-xl px-3"
          >
            <option value={LLMProvider.openai_compat}>openai_compat</option>
            <option value={LLMProvider.openai}>openai</option>
            <option value={LLMProvider.anthropic}>anthropic</option>
          </select>
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
            {t('auditLlmModel')}
          </span>
          <input
            type="text"
            value={auditModelVal}
            onChange={(e) => setAuditModel(e.target.value)}
            placeholder={t('auditLlmModelPh')}
            className="gf-input h-10 w-full rounded-xl px-3"
          />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
            {t('auditLlmApikey')}
          </span>
          <input
            type="password"
            value={auditApikeyVal}
            onChange={(e) => setAuditApikey(e.target.value)}
            placeholder={t('auditLlmApikeyPh')}
            className="gf-input h-10 w-full rounded-xl px-3"
          />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="gf-page-muted text-[11px] font-medium uppercase tracking-wider">
            {t('auditLlmBaseUrl')}
          </span>
          <input
            type="text"
            value={auditBaseUrlVal}
            onChange={(e) => setAuditBaseUrl(e.target.value)}
            placeholder={t('auditLlmBaseUrlPh')}
            className="gf-input h-10 w-full rounded-xl px-3"
          />
        </label>
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="gf-interactive gf-btn-primary inline-flex h-10 cursor-pointer items-center justify-center gap-2 px-5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
            disabled={saveMu.isPending || !auditModelVal.trim()}
            onClick={() => saveMu.mutate()}
          >
            {saveMu.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t('save')}
          </button>
          <button
            type="button"
            className="gf-interactive inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-xl border px-5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
            disabled={auditTestMu.isPending || !auditModelVal.trim()}
            onClick={() => auditTestMu.mutate()}
          >
            {auditTestMu.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t('auditLlmTest')}
          </button>
        </div>
      </section>

      {disableAuditConfirmOpen ? (
        <ConfirmModal
          title={t('auditLlmDisableTitle')}
          danger
          confirmLabel={t('auditLlmDisableConfirm')}
          onClose={() => setDisableAuditConfirmOpen(false)}
          onConfirm={() => {
            setAuditEnabled(false)
            setDisableAuditConfirmOpen(false)
          }}
        >
          <p className="text-sm leading-relaxed text-[var(--gf-text-muted)]">
            {t('auditLlmDisableWarning')}
          </p>
        </ConfirmModal>
      ) : null}
    </div>
  )
}
