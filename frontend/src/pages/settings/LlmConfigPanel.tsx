import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Star, Trash2 } from 'lucide-react'
import { LLMProvider } from '@/api/enums'
import { ApiError } from '@/api/errors'
import { meApi } from '@/api/me'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth-store'

const providers = [
  { id: LLMProvider.anthropic, label: 'Anthropic' },
  { id: LLMProvider.openai, label: 'OpenAI' },
  { id: LLMProvider.openai_compat, label: 'OpenAI Compatible' },
] as const

export function LlmConfigPanel() {
  const token = useAuthStore((s) => s.access_token)
  const qc = useQueryClient()
  const [provider, setProvider] = useState<LLMProvider>(LLMProvider.anthropic)
  const [model, setModel] = useState('claude-sonnet-4-20250514')
  const [apikey, setApikey] = useState('')
  const [isDefault, setIsDefault] = useState(true)
  const [msg, setMsg] = useState<string | null>(null)

  const list = useQuery({
    queryKey: ['llm-configs'],
    enabled: Boolean(token),
    queryFn: () => meApi.listLlmConfigs(token!),
  })

  const createMu = useMutation({
    mutationFn: () =>
      meApi.createLlmConfig(
        { provider, model, apikey, is_default: isDefault },
        token!,
      ),
    onSuccess: () => {
      setApikey('')
      setMsg('已保存并连通测试通过')
      void qc.invalidateQueries({ queryKey: ['llm-configs'] })
    },
    onError: (e) => setMsg(e instanceof ApiError ? e.message : '保存失败'),
  })

  const testMu = useMutation({
    mutationFn: (id: string) => meApi.testLlmConfig(id, token!),
    onSuccess: (r) => setMsg(r.tested_ok ? '连通测试通过' : r.error ?? '连通失败'),
    onError: (e) => setMsg(e instanceof ApiError ? e.message : '测试失败'),
  })

  const defaultMu = useMutation({
    mutationFn: (id: string) => meApi.patchLlmConfig(id, { is_default: true }, token!),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['llm-configs'] }),
  })

  const delMu = useMutation({
    mutationFn: (id: string) => meApi.deleteLlmConfig(id, token!),
    onSuccess: () => {
      setMsg('已删除')
      void qc.invalidateQueries({ queryKey: ['llm-configs'] })
    },
    onError: (e) => setMsg(e instanceof ApiError ? e.message : '删除失败'),
  })

  return (
    <section className="space-y-4 rounded-2xl border border-white/[0.08] bg-[#12151a] p-5">
      <div>
        <h2 className="text-lg text-white/90">LLM 配置</h2>
        <p className="mt-1 text-sm text-white/40">用户自带 apikey；保存前做连通测试，前端只展示掩码。</p>
      </div>

      {msg ? <p className="text-sm text-teal-200/80">{msg}</p> : null}

      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-1.5 text-sm">
          <span className="font-mono text-[10px] text-white/40 uppercase">Provider</span>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as LLMProvider)}
            className="h-10 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-white outline-none"
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-mono text-[10px] text-white/40 uppercase">Model</span>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="h-10 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-white outline-none"
          />
        </label>
        <label className="space-y-1.5 text-sm md:col-span-2">
          <span className="font-mono text-[10px] text-white/40 uppercase">API Key</span>
          <input
            type="password"
            value={apikey}
            onChange={(e) => setApikey(e.target.value)}
            placeholder="sk-..."
            className="h-10 w-full rounded-xl border border-white/10 bg-black/30 px-3 text-white outline-none"
          />
        </label>
      </div>

      <label className="flex items-center gap-2 text-sm text-white/60">
        <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} />
        设为默认
      </label>

      <Button
        className="!rounded-lg !bg-teal-400 !text-black hover:!bg-teal-300"
        disabled={!apikey || createMu.isPending}
        onClick={() => createMu.mutate()}
      >
        {createMu.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        保存并测试
      </Button>

      <ul className="space-y-2">
        {(list.data ?? []).map((c) => (
          <li
            key={c.config_id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-black/25 px-3 py-3 ring-1 ring-white/[0.04]"
          >
            <div>
              <p className="text-sm text-white/90">
                {c.provider} · {c.model}
                {c.is_default ? (
                  <span className="ml-2 font-mono text-[10px] text-teal-300">DEFAULT</span>
                ) : null}
              </p>
              <p className="mt-0.5 font-mono text-xs text-white/40">{c.apikey_masked}</p>
            </div>
            <div className="flex gap-1.5">
              <Button
                variant="ghost"
                className="!rounded-lg !px-2 !py-1.5 text-xs text-white/60"
                onClick={() => testMu.mutate(c.config_id)}
              >
                测试
              </Button>
              {!c.is_default ? (
                <Button
                  variant="ghost"
                  className="!rounded-lg !px-2 !py-1.5 text-xs text-white/60"
                  onClick={() => defaultMu.mutate(c.config_id)}
                >
                  <Star className="h-3.5 w-3.5" />
                  默认
                </Button>
              ) : null}
              {!c.is_default ? (
                <Button
                  variant="ghost"
                  className="!rounded-lg !px-2 !py-1.5 text-xs text-red-200/70"
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
