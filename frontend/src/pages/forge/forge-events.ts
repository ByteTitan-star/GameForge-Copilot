import { RunPhase, WSEventType } from '@/api/enums'
import type { HitlWaitPayload, WsEnvelope } from '@/api/types.gen'
import { mockDb } from '@/mocks/db'
import type { TimelineItem } from '@/components/forge/RunTimeline'
import type { ChatMsg } from '@/components/forge/ChatPanel'

export type ForgeEventHandlers = {
  setPhase: (p: RunPhase | 'idle' | 'paused') => void
  pushItem: (partial: Omit<TimelineItem, 'id' | 'at'> & { at?: string }) => void
  setHitl: (p: HitlWaitPayload | null) => void
  setBusy: (v: boolean) => void
  setPreviewUrl: (url: string | null) => void
  setSideTab: (t: 'log' | 'play') => void
  appendMessages: (msgs: ChatMsg[]) => void
  gameId: string | undefined
}

function mid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

export function handleForgeWsEvent(ev: WsEnvelope, h: ForgeEventHandlers) {
  const p = ev.payload
  switch (ev.type) {
    case WSEventType.phase_start:
      h.setPhase(p.phase as RunPhase)
      h.pushItem({ label: `phase_start · ${String(p.phase)}`, tone: 'info', at: ev.ts })
      return
    case WSEventType.llm_call:
      h.pushItem({
        label: `llm_call · ${String(p.model)}`,
        detail: `${String(p.provider)} · ${String(p.input_tokens)}→${String(p.output_tokens)} tokens`,
        tone: 'muted',
        at: ev.ts,
      })
      return
    case WSEventType.tool_call:
      h.pushItem({
        label: `tool_call · ${String(p.tool)}`,
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
        label: 'hitl_wait · 等待策划确认',
        detail: payload.design_doc.title,
        tone: 'warn',
        at: ev.ts,
      })
      h.appendMessages([
        {
          id: mid('m'),
          role: 'assistant',
          content: `策划稿已就绪：《${payload.design_doc.title}》。请在中间面板确认或修改后继续。`,
        },
      ])
      return
    }
    case WSEventType.build_done: {
      const url = `/mock-play.html?game=${encodeURIComponent(h.gameId ?? '')}&v=${encodeURIComponent(String(p.version))}`
      h.setPreviewUrl(url)
      h.pushItem({
        label: `build_done · v${String(p.version)}`,
        detail: String(p.artifact_path ?? ''),
        tone: 'ok',
        at: ev.ts,
      })
      return
    }
    case WSEventType.qa_report:
      h.pushItem({
        label: p.passed ? 'qa_report · passed' : 'qa_report · failed',
        detail: Array.isArray(p.issues) ? (p.issues as string[]).join(' · ') : String(p.log_excerpt ?? ''),
        tone: p.passed ? 'ok' : 'err',
        at: ev.ts,
      })
      return
    case WSEventType.done:
      applyDone(ev, h)
      return
    case WSEventType.error:
      h.setBusy(false)
      h.setPhase('idle')
      h.pushItem({
        label: `error · ${String(p.code)}`,
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
  if (gid) {
    const g = mockDb.games.find((x) => x.game_id === gid)
    if (g) {
      g.current_version = Math.max(g.current_version, ver)
      g.updated_at = new Date().toISOString()
    }
  }
  const url = `/mock-play.html?game=${encodeURIComponent(gid)}&v=${encodeURIComponent(String(ver))}`
  h.setPreviewUrl(url)
  h.pushItem({ label: 'done · 生成完成', detail: url, tone: 'ok', at: ev.ts })
  h.appendMessages([
    {
      id: mid('m'),
      role: 'assistant',
      content: `构建完成（v${ver}）。右侧可直接试玩；满意后可到「我的游戏」提交发布。`,
    },
  ])
}
