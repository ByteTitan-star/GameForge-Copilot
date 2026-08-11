import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Star, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { LLMProvider } from '@/api/enums'
import { formatApiError } from '@/api/error-message'
import { meApi } from '@/api/me'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'
import { isTrialUser } from '@/lib/trial'
import { useAuthStore } from '@/stores/auth-store'

const providers = [
  { id: LLMProvider.anthropic, label: 'Anthropic' },
  { id: LLMProvider.openai, label: 'OpenAI' },
  { id: LLMProvider.openai_compat, label: 'OpenAI Compatible' },
] as const

const defaultModels: Record<LLMProvider, string> = {
  [LLMProvider.anthropic]: 'claude-sonnet-4-20250514',
  [LLMProvider.openai]: 'gpt-4o',
  [LLMProvider.openai_compat]: '',
}

const defaultBaseUrls: Record<LLMProvider, string> = {
  [LLMProvider.anthropic]: 'https://api.anthropic.com/v1',
  [LLMProvider.openai]: 'https://api.openai.com/v1',
  [LLMProvider.openai_compat]: '',
}

function normalizeBaseUrl(provider: LLMProvider, value: string): string | null {
  const trimmed = value.trim()
  if (trimmed) return trimmed
  if (provider === LLMProvider.openai_compat) return null
  return null
}

export function LlmConfigPanel() {
  const t = useT()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const trial = isTrialUser(user)
  const qc = useQueryClient()
  const [provider, setProvider] = useState<LLMProvider>(LLMProvider.anthropic)
  const [model, setModel] = useState(defaultModels[LLMProvider.anthropic])
  const [apikey, setApikey] = useState('')
  const [baseUrl, setBaseUrl] = useState(defaultBaseUrls[LLMProvider.anthropic])
  const [isDefault, setIsDefault] = useState(true)
  const [msg, setMsg] = useState<string | null>(null)

  const list = useQuery({
    queryKey: ['llm-configs'],
    enabled: Boolean(token),
    queryFn: () => meApi.listLlmConfigs(token!),
  })

  const models = useQuery({
    queryKey: ['llm-models', provider, baseUrl],
    enabled: Boolean(token),
    queryFn: () => meApi.listModels(token!, provider),
  })

  const draftBody = () => ({
    provider,
    model: model.trim(),
    apikey,
    base_url: normalizeBaseUrl(provider, baseUrl),
  })

  const formInvalid =
    trial ||
    !apikey.trim() ||
    !model.trim() ||
    (provider === LLMProvider.openai_compat && !baseUrl.trim())

  const createMu = useMutation({
    mutationFn: () => meApi.createLlmConfig({ ...draftBody(), is_default: isDefault }, token!),
    onSuccess: () => {
      setApikey('')
      setMsg(t('llmSavedOk'))
      void qc.invalidateQueries({ queryKey: ['llm-configs'] })
    },
    onError: (e) => setMsg(formatApiError(e, t('llmSaveFailed'))),
  })

  const dryTestMu = useMutation({
    mutationFn: () => meApi.testLlmConfigDraft(draftBody(), token!),
    onSuccess: (r) => setMsg(r.tested_ok ? t('llmTestOk') : r.error ?? t('llmTestFail')),
    onError: (e) => setMsg(formatApiError(e, t('llmTestFailed'))),
  })

  const testMu = useMutation({
    mutationFn: (id: string) => meApi.testLlmConfig(id, token!),
    onSuccess: (r) => setMsg(r.tested_ok ? t('llmTestOk') : r.error ?? t('llmTestFail')),
    onError: (e) => setMsg(formatApiError(e, t('llmTestFailed'))),
  })

  const defaultMu = useMutation({
    mutationFn: (id: string) => meApi.patchLlmConfig(id, { is_default: true }, token!),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['llm-configs'] }),
  })

  const delMu = useMutation({
    mutationFn: (id: string) => meApi.deleteLlmConfig(id, token!),
    onSuccess: () => {
      setMsg(t('llmDeleted'))
      void qc.invalidateQueries({ queryKey: ['llm-configs'] })
    },
    onError: (e) => setMsg(formatApiError(e, t('llmDeleteFailed'))),
  })

  const onProviderChange = (next: LLMProvider) => {
    setProvider(next)
    setModel(defaultModels[next])
    setBaseUrl(defaultBaseUrls[next])
  }

  return (
    <section className="gf-glass space-y-4 rounded-2xl p-5">
      <div>
        <h2 className="gf-page-body text-lg">{t('llmTitle')}</h2>
        <p className="mt-1 gf-page-muted text-sm">{t('llmSubtitle')}</p>
      </div>

      {trial ? (
        <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {t('trialLlmLocked')}
        </p>
      ) : null}

      {msg ? <p className="text-sm gf-page-body">{msg}</p> : null}
      {list.isError ? (
        <p role="alert" className="text-sm text-rose-500">
          {t('llmConfigLoadFailed')} {formatApiError(list.error)}
        </p>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-1.5 text-sm">
          <span className="font-mono text-[10px] gf-page-muted uppercase">Provider</span>
          <select
            value={provider}
            onChange={(e) => onProviderChange(e.target.value as LLMProvider)}
            disabled={trial}
            className="h-10 w-full rounded-xl gf-input px-3 disabled:opacity-50"
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-mono text-[10px] gf-page-muted uppercase">Model</span>
          <input
            list="llm-model-options"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={trial}
            placeholder={t('llmModelPlaceholder')}
            className="h-10 w-full rounded-xl gf-input px-3 disabled:opacity-50"
          />
          <datalist id="llm-model-options">
            {(models.data ?? []).map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          {models.isFetching ? (
            <span className="font-mono text-[10px] gf-page-muted">{t('llmFetchingModels')}</span>
          ) : null}
        </label>
        <label className="space-y-1.5 text-sm md:col-span-2">
          <span className="font-mono text-[10px] gf-page-muted uppercase">API Key</span>
          <input
            type="password"
            value={apikey}
            onChange={(e) => setApikey(e.target.value)}
            placeholder="sk-..."
            disabled={trial}
            className="h-10 w-full rounded-xl gf-input px-3 disabled:opacity-50"
          />
        </label>
        <label className="space-y-1.5 text-sm md:col-span-2">
          <span className="font-mono text-[10px] gf-page-muted uppercase">Base URL</span>
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={
              provider === LLMProvider.openai_compat
                ? 'https://api.example.com/v1'
                : t('llmBaseUrlOptional')
            }
            required={provider === LLMProvider.openai_compat}
            disabled={trial}
            className="h-10 w-full rounded-xl gf-input px-3 disabled:opacity-50"
          />
        </label>
      </div>

      <label className="flex items-center gap-2 text-sm gf-page-muted">
        <input
          type="checkbox"
          checked={isDefault}
          onChange={(e) => setIsDefault(e.target.checked)}
          disabled={trial}
        />
        {t('llmSetDefault')}
      </label>

      <div className="flex flex-wrap gap-2">
        <Button
          variant="ghost"
          className="!rounded-lg gf-page-muted"
          disabled={formInvalid || dryTestMu.isPending}
          onClick={() => dryTestMu.mutate()}
        >
          {dryTestMu.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {t('llmTestOnly')}
        </Button>
        <Button
          className="!rounded-lg !bg-teal-400 !text-black hover:!bg-teal-300"
          disabled={formInvalid || createMu.isPending}
          onClick={() => createMu.mutate()}
        >
          {createMu.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {t('llmSaveAndTest')}
        </Button>
      </div>

      <ul className="space-y-2">
        {(list.data ?? []).map((c) => (
          <li
            key={c.config_id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-black/[0.02] px-3 py-3 ring-1 ring-[var(--gf-border)]"
          >
            <div>
              <p className="text-sm gf-page-body">
                {c.provider} · {c.model}
                {c.is_default ? (
                  <span className="ml-2 font-mono text-[10px] gf-text-accent">DEFAULT</span>
                ) : null}
              </p>
              <p className="mt-0.5 font-mono text-xs gf-page-muted">{c.apikey_masked}</p>
              {c.base_url ? (
                <p className="mt-0.5 font-mono text-[10px] gf-page-muted">{c.base_url}</p>
              ) : null}
            </div>
            <div className="flex gap-1.5">
              <Button
                variant="ghost"
                className="!rounded-lg !px-2 !py-1.5 text-xs gf-page-muted"
                disabled={trial || testMu.isPending}
                onClick={() => testMu.mutate(c.config_id)}
              >
                {t('llmTest')}
              </Button>
              {!c.is_default ? (
                <Button
                  variant="ghost"
                  className="!rounded-lg !px-2 !py-1.5 text-xs gf-page-muted"
                  disabled={trial}
                  onClick={() => defaultMu.mutate(c.config_id)}
                >
                  <Star className="h-3.5 w-3.5" />
                  {t('llmDefault')}
                </Button>
              ) : null}
              {!c.is_default ? (
                <Button
                  variant="ghost"
                  className="!rounded-lg !px-2 !py-1.5 text-xs text-red-600"
                  disabled={trial}
                  onClick={() => delMu.mutate(c.config_id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
