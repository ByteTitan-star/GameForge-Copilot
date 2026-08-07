import { RunPhase, WSEventType } from '@/api/enums'
import type { HitlWaitPayload, WsEnvelope } from '@/api/ws-types'
import type { TimelineItem } from '@/components/forge/RunTimeline'
import type { ChatMsg } from '@/components/forge/ChatPanel'
import type { MessageKey } from '@/i18n/messages'
import { resolveHostingUrl } from '@/lib/hosting'

export type ForgeEventHandlers = {
  setPhase: (p: RunPhase | 'idle' | 'paused') => void
  pushItem: (partial: Omit<TimelineItem, 'id' | 'at'> & { at?: string }) => void
  setHitl: (p: HitlWaitPayload | null) => void
  setBusy: (v: boolean) => void
  setPreviewUrl: (url: string | null) => void
  setSideTab: (t: 'log' | 'play') => void
  appendMessages: (msgs: ChatMsg[]) => void
  setQuotaHint?: (text: string | null) => void
  gameId: string | undefined
  t: (key: MessageKey) => string
}

function mid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
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
    case WSEventType.phase_start:
      h.setPhase(p.phase as RunPhase)
      h.pushItem({
        label: `${h.t('phaseStarted')} · ${phaseLabel[p.phase as RunPhase] ?? String(p.phase)}`,
        tone: 'info',
        at: ev.ts,
      })
      return
    case WSEventType.llm_call:
      h.pushItem({
        label: h.t('modelCall'),
        detail: `${String(p.model)} · ${String(p.input_tokens)}→${String(p.output_tokens)}`,
        tone: 'muted',
        at: ev.ts,
      })
      return
    case WSEventType.tool_call:
      h.pushItem({
        label: h.t('toolCall'),
        detail: String(p.summary ?? ''),
        tone: p.status === 'ok' ? 'ok' : 'err',
        at: ev.ts,
      })
      return
    case WSEventType.hitl_wait: {
      const payload = p as unknown as HitlWaitPayload
      h.setHitl(payload)
      h.setPhase('paused')
      h.setBusy(false)
      h.pushItem({
        label: h.t('humanReviewWaiting'),
        detail: payload.design_doc.title,
        tone: 'warn',
        at: ev.ts,
      })
      h.appendMessages([
        {
          id: mid('m'),
          role: 'assistant',
          content: `${h.t('confirmDesign')}：${payload.design_doc.title}。${h.t('continueAfterApproval')}。`,
        },
      ])
      return
    }
    case WSEventType.build_done: {
      const url = previewFromPayload(p, h.gameId, p.version)
      if (url) h.setPreviewUrl(url)
      h.pushItem({
        label: `${h.t('buildComplete')} · v${String(p.version)}`,
        tone: 'ok',
        at: ev.ts,
      })
      return
    }
    case WSEventType.qa_report:
      h.pushItem({
        label: p.passed ? h.t('qaPassed') : h.t('qaFailed'),
        detail: Array.isArray(p.issues) ? (p.issues as string[]).join(' · ') : String(p.log_excerpt ?? ''),
        tone: p.passed ? 'ok' : 'err',
        at: ev.ts,
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
    case WSEventType.error:
      h.setBusy(false)
      h.setPhase('idle')
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

function applyDone(ev: WsEnvelope, h: ForgeEventHandlers) {
  const p = ev.payload
  h.setPhase(RunPhase.done)
  h.setBusy(false)
  h.setSideTab('play')
  const ver = Number(p.version ?? 1)
  const gid = String(p.game_id ?? h.gameId ?? '')
  const url = previewFromPayload(p, gid || h.gameId, ver)
  if (url) h.setPreviewUrl(url)
  h.pushItem({ label: h.t('generationComplete'), detail: url ?? undefined, tone: 'ok', at: ev.ts })
  h.appendMessages([
    {
      id: mid('m'),
      role: 'assistant',
      content: `${h.t('playReady')}（v${ver}）。${h.t('describeIteration')}`,
    },
  ])
}
