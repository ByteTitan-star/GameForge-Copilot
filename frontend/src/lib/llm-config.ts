import type { LlmConfig } from '@/api/types'

/** 选择默认 LLM 配置 id；无配置时返回 null */
export function pickDefaultLlmConfigId(configs: LlmConfig[]): string | null {
  if (configs.length === 0) return null
  const def = configs.find((c) => c.is_default)
  return def?.config_id ?? configs[0]?.config_id ?? null
}
