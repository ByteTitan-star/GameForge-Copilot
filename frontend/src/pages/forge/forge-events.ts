import { RunPhase, RunStatus, WSEventType } from '@/api/enums'
import type { AttackedPayload, HitlWaitPayload, WsEnvelope } from '@/api/ws-types'
import type { TimelineItem } from '@/components/forge/RunTimeline'
import type { ChatMsg } from '@/components/forge/ChatPanel'
import type { MessageKey } from '@/i18n/messages'
import { resolveHostingUrl } from '@/lib/hosting'
import { parseDesignDoc } from '@/lib/hitl-design-doc'
import { PIPELINE_PHASES } from '@/lib/phase-labels'

import type { StagePipelineState } from '@/lib/stage-pipeline-state'
import {
  applyPhaseStart,
  markAllDone,
  markStageFailed,
} from '@/lib/stage-pipeline-state'

export type ForgeEventHandlers = {
  setPhase: (p: RunPhase | 'idle' | 'paused') => void
  pushItem: (partial: Omit<TimelineItem, 'id' | 'at'> & { at?: string }) => void
  setHitl: (p: HitlWaitPayload | null) => void
  setBusy: (v: boolean) => void
  setRunStatus?: (status: RunStatus | 'idle') => void
  setPreviewUrl: (url: string | null) => void
  setPreviewVersion?: (version: number | null) => void
  setSideTab: (t: 'log' | 'play') => void
  appendMessages: (msgs: ChatMsg[], kind?: 'design' | 'completed' | 'thinking') => void
  /** LLM 流式微批增量：把 delta 追加到正在生成的 assistant 消息（打字机效果）。 */
  appendLlmDelta?: (phase: RunPhase, text: string) => void
  /** 把「正在生成」的流式消息落定为正式消息（阶段切换/done/attacked 时调用）。 */
  flushStreamingMessage?: () => void
  /** 内容审核命中：断 WS + 弹友好提示 + 清理 run 状态。 */
  onAttacked?: (p: AttackedPayload) => void
  setQuotaHint?: (text: string | null) => void
  setCurrentModel?: (model: string | null) => void
  setRunError?: (runId: string, message: string) => void
  setStagePipeline?: (updater: (prev: StagePipelineState) => StagePipelineState) => void
  onRunFinished?: () => void
  /** done 事件触发时的「自动打开试玩区」回调；由调用方按用户是否手动操作过试玩区来决定是否真正打开。 */
  onStageAutoOpen?: () => void
  gameId: string | undefined
  runId?: string | null
  /** 用户已主动取消该 run：后续失败事件不再记为报错。 */
  isUserCancelled?: (runId: string) => boolean
  t: (key: MessageKey) => string
}

function mid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

function toolCallPhase(raw: unknown): RunPhase | undefined {
  const value = String(raw ?? '')
  if (value === 'repair' || value === 'diagnose') return RunPhase.code
  if (value === 'art_options' || value === 'art_detail' || value === 'revise_art_options') {
    return RunPhase.art
  }
  return PIPELINE_PHASES.includes(value as RunPhase) ? (value as RunPhase) : undefined
}

function skillDetail(p: Record<string, unknown>): string {
  const args = p.args
  if (args && typeof args === 'object') {
    const rec = args as { skill_names?: unknown; skill_ids?: unknown }
    if (Array.isArray(rec.skill_names) && rec.skill_names.length) {
      return rec.skill_names.map(String).join(', ')
    }
    if (Array.isArray(rec.skill_ids) && rec.skill_ids.length) {
      return rec.skill_ids.map(String).join(', ')
    }
  }
  return String(p.summary ?? '')
}

function isUserCancelPayload(p: Record<string, unknown>, h: ForgeEventHandlers): boolean {
  if (h.runId && h.isUserCancelled?.(h.runId)) return true
  const code = String(p.code ?? '')
  const message = String(p.message ?? '')
  return (
    code === 'CANCELLED' ||
    /用户取消/.test(message) ||
    /cancelled by user|canceled by user/i.test(message)
  )
}

function previewFromPayload(
  payload: Record<string, unknown>,
  gameId: string | undefined,
  versionFallback?: unknown,
): string | null {
  const fromEvent = payload.preview_url
  if (typeof fromEvent === 'string' && fromEvent) return resolveHostingUrl(fromEvent)
  const ver = versionFallback ?? payload.version
  if (gameId && ver != null) return resolveHostingUrl(`/draft/${gameId}/${ver}`)
  return null
}

export function handleForgeWsEvent(ev: WsEnvelope, h: ForgeEventHandlers) {
  const p = ev.payload
  const phaseLabel: Record<RunPhase, string> = {
    [RunPhase.plan]: h.t('phasePlan'),
    [RunPhase.art]: h.t('phaseArt'),
    [RunPhase.code]: h.t('phaseCode'),
    [RunPhase.qa]: h.t('phaseQa'),
    [RunPhase.done]: h.t('phaseDone'),
  }
  switch (ev.type) {
    case WSEventType.phase_start: {
      // 新阶段开始：把上一阶段打字机攒的流式消息落定，避免串到新阶段。
      h.flushStreamingMessage?.()
      const phase = p.phase as RunPhase
      // phase_start 表示后端已经离开人工确认检查点。WS 重放时也必须清除先前
      // replay 出来的 hitl_wait，否则任务完成后页面仍会保留一张点击必 409 的旧卡。
      h.setHitl(null)
      h.setPhase(phase)
      h.setBusy(true)
      h.setRunStatus?.(RunStatus.running)
      const humanLabel = typeof p.human_label === 'string' ? p.human_label : undefined
      const etaSeconds = typeof p.eta_seconds === 'number' ? p.eta_seconds : undefined
      h.setStagePipeline?.((prev) => applyPhaseStart(prev, phase, humanLabel, etaSeconds))
      h.pushItem({
        label: humanLabel ?? `${h.t('phaseStarted')} · ${phaseLabel[phase] ?? String(phase)}`,
        detail: etaSeconds ? `~${Math.round(etaSeconds / 60)}min` : undefined,
        tone: 'info',
        at: ev.ts,
        phase,
      })
      // art 节点不调 LLM（只选素材）执行极快，仅靠进度条一闪而过会让用户误以为
      // 「美术没完成就跳到开发」。把各阶段进入消息也推进对话流，确保阶段切换在主区域可见。
      const phaseStartedKey: Partial<Record<RunPhase, MessageKey>> = {
        [RunPhase.plan]: 'phasePlanStarted',
        [RunPhase.art]: 'phaseArtStarted',
        [RunPhase.code]: 'phaseCodeStarted',
        [RunPhase.qa]: 'phaseQaStarted',
      }
      const startedKey = phaseStartedKey[phase]
      if (startedKey) {
        h.appendMessages(
          [{ id: mid('m'), role: 'assistant', content: h.t(startedKey), kind: 'thinking' }],
          'thinking',
        )
      }
      return
    }
    case WSEventType.llm_call:
      // 一轮 LLM 调用结束：把打字机攒的流式消息落定，再记一条用量日志。
      h.flushStreamingMessage?.()
      h.setCurrentModel?.(String(p.model ?? ''))
      h.pushItem({
        label: h.t('modelCall'),
        detail: `${String(p.model)} · ${String(p.input_tokens)}→${String(p.output_tokens)}`,
        tone: 'muted',
        at: ev.ts,
        phase: (p.phase as RunPhase | undefined) ?? undefined,
      })
      return
    case WSEventType.llm_delta: {
      // LLM 流式微批增量：追加到正在生成的 assistant 消息（打字机效果）。
      // 不记入 RunTimeline（会瞬间吃满额度 + 倒序展示不符阅读直觉）。
      const phase = p.phase as RunPhase
      const delta = typeof p.delta === 'string' ? p.delta : ''
      if (delta) h.appendLlmDelta?.(phase, delta)
      return
    }
    case WSEventType.tool_call:
      if (p.status !== 'ok' && isUserCancelPayload(p, h)) return
      h.pushItem({
        label: p.tool === 'skill' ? h.t('skillCall') : h.t('toolCall'),
        detail: p.tool === 'skill' ? skillDetail(p) : String(p.summary ?? ''),
        tone: p.status === 'ok' ? 'ok' : 'err',
        at: ev.ts,
        phase: toolCallPhase(p.phase),
      })
      return
    case WSEventType.hitl_wait: {
      // 进入人工确认：把打字机攒的流式消息落定为正式消息。
      h.flushStreamingMessage?.()
      const payload = p as unknown as HitlWaitPayload
      h.setHitl(payload)
      h.setPhase('paused')
      h.setBusy(false)
      h.setRunStatus?.(RunStatus.paused)
      const doc = parseDesignDoc(payload.design_doc)
      const isArtReview = payload.node === 'art_confirm'
      const artNames = payload.art_options?.options.map((option) => option.name).join(' / ')
      h.pushItem({
        label: h.t('humanReviewWaiting'),
        detail: isArtReview ? artNames || payload.node : doc.title || payload.node,
        tone: 'warn',
        at: ev.ts,
        phase: isArtReview ? RunPhase.art : RunPhase.plan,
      })
      h.appendMessages(
        [
          {
            id: mid('m'),
            role: 'assistant',
            kind: 'thinking',
            content: isArtReview
              ? `${h.t('chooseArtDirection')}：${artNames || payload.node}`
              : `${h.t('confirmDesign')}：${doc.title || payload.node}。${h.t('continueAfterApproval')}。`,
          },
        ],
        'thinking',
      )
      return
    }
    case WSEventType.build_done: {
      const url = previewFromPayload(p, h.gameId, p.version)
      if (url) h.setPreviewUrl(url)
      if (typeof p.version === 'number') h.setPreviewVersion?.(p.version)
      h.pushItem({
        label: `${h.t('buildComplete')} · v${String(p.version)}`,
        tone: 'ok',
        at: ev.ts,
        phase: RunPhase.code,
      })
      return
    }
    case WSEventType.qa_report:
      if (!p.passed) {
        h.setStagePipeline?.((prev) => markStageFailed(prev, RunPhase.qa))
      }
      h.pushItem({
        label: p.passed ? h.t('qaPassed') : h.t('qaFailed'),
        detail: Array.isArray(p.issues) ? (p.issues as string[]).join(' · ') : String(p.log_excerpt ?? ''),
        tone: p.passed ? 'ok' : 'err',
        at: ev.ts,
        phase: RunPhase.qa,
      })
      return
    case WSEventType.usage: {
      const used = Number(p.today_used ?? 0)
      const remain = Number(p.remaining ?? 0)
      const limit = Number(p.daily_limit ?? 0)
      h.setQuotaHint?.(
        `${h.t('quotaHint')}: ${used.toLocaleString()} / ${limit.toLocaleString()} · ${h.t('remaining')} ${remain.toLocaleString()}`,
      )
      h.pushItem({
        label: h.t('usageUpdated'),
        detail: `remaining=${remain}`,
        tone: 'muted',
        at: ev.ts,
      })
      return
    }
    case WSEventType.done:
      applyDone(ev, h)
      return
    case WSEventType.attacked: {
      // 内容审核命中：落定流式消息 → 交给 onAttacked 断 WS + 弹友好提示 + 清理 run。
      // 后端紧随会发 ERROR(CONTENT_BLOCKED, fatal)，error case 会再做一次幂等清理。
      h.flushStreamingMessage?.()
      h.setBusy(false)
      h.setRunStatus?.(RunStatus.failed)
      const payload = p as unknown as AttackedPayload
      h.onAttacked?.(payload)
      h.pushItem({
        label: h.t('contentBlocked'),
        detail: payload.message,
        tone: 'err',
        at: ev.ts,
      })
      return
    }
    case WSEventType.error:
      if (isUserCancelPayload(p, h)) {
        applyUserCancelled(ev, h)
        return
      }
      h.setHitl(null)
      h.setBusy(false)
      h.setRunStatus?.(RunStatus.failed)
      h.setPhase('idle')
      h.onRunFinished?.()
      if (h.runId) h.setRunError?.(h.runId, String(p.message))
      h.setStagePipeline?.((prev) => markStageFailed(prev, RunPhase.code))
      h.pushItem({
        label: `${h.t('generationError')} · ${String(p.code)}`,
        detail: String(p.message),
        tone: 'err',
        at: ev.ts,
      })
      return
    default:
      h.pushItem({ label: String(ev.type), tone: 'muted', at: ev.ts })
  }
}

function applyUserCancelled(ev: WsEnvelope, h: ForgeEventHandlers) {
  const p = ev.payload
  h.flushStreamingMessage?.()
  h.setHitl(null)
  h.setBusy(false)
  h.setRunStatus?.(RunStatus.cancelled)
  h.setPhase('idle')
  h.onRunFinished?.()
  h.pushItem({
    label: h.t('runCancelled'),
    detail: String(p.message ?? ''),
    tone: 'warn',
    at: ev.ts,
  })
}

function applyDone(ev: WsEnvelope, h: ForgeEventHandlers) {
  const p = ev.payload
  h.flushStreamingMessage?.()
  h.setHitl(null)
  h.setPhase(RunPhase.done)
  h.setBusy(false)
  h.setRunStatus?.(RunStatus.done)
  h.onRunFinished?.()
  h.setStagePipeline?.((prev) => markAllDone(prev))
  h.setSideTab('play')
  const ver = Number(p.version ?? 1)
  const gid = String(p.game_id ?? h.gameId ?? '')
  const url = previewFromPayload(p, gid || h.gameId, ver)
  if (url) h.setPreviewUrl(url)
  h.setPreviewVersion?.(ver)
  // 四阶段全部跑完，触发「自动打开试玩区」；是否真正打开由调用方按用户手动操作记录决定。
  h.onStageAutoOpen?.()
  h.pushItem({ label: h.t('generationComplete'), detail: url ?? undefined, tone: 'ok', at: ev.ts, phase: RunPhase.qa })
  const doneText =
    typeof p.message === 'string' && p.message.trim()
      ? p.message
      : `${h.t('playReady')}（v${ver}）。${h.t('describeIteration')}`
  h.appendMessages(
    [
      {
        id: mid('m'),
        role: 'assistant',
        kind: 'completed',
        content: doneText,
      },
    ],
    'completed',
  )
}
