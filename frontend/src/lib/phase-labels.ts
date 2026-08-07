import { RunPhase } from '@/api/enums'
import type { MessageKey } from '@/i18n/messages'

/** WS 无 human_label 时的 fallback（与后端 phase_labels 语义对齐） */
export const PHASE_HUMAN_LABEL_KEYS: Record<RunPhase, MessageKey> = {
  [RunPhase.plan]: 'stageHumanPlan',
  [RunPhase.art]: 'stageHumanArt',
  [RunPhase.code]: 'stageHumanCode',
  [RunPhase.qa]: 'stageHumanQa',
  [RunPhase.done]: 'stageHumanDone',
}

/** 静态 ETA 秒数 fallback（P50 区间中值） */
export const PHASE_ETA_SECONDS: Record<RunPhase, number> = {
  [RunPhase.plan]: 90,
  [RunPhase.art]: 60,
  [RunPhase.code]: 120,
  [RunPhase.qa]: 45,
  [RunPhase.done]: 0,
}

export const PIPELINE_PHASES: RunPhase[] = [
  RunPhase.plan,
  RunPhase.art,
  RunPhase.code,
  RunPhase.qa,
]

export function formatEtaSeconds(seconds: number, t: (k: MessageKey) => string): string {
  if (seconds <= 0) return ''
  const min = Math.max(1, Math.round(seconds / 60))
  return t('stageEtaMinutes').replace('{n}', String(min))
}
