import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Rocket } from 'lucide-react'
import { gamesApi } from '@/api/games'
import { RunPhase } from '@/api/enums'
import { ApiError } from '@/api/errors'
import type { HitlWaitPayload } from '@/api/types.gen'
import { ChatPanel, type ChatMsg } from '@/components/forge/ChatPanel'
import { HitlCard } from '@/components/forge/HitlCard'
import { ForgeSidePanel } from '@/components/forge/ForgeSidePanel'
import { RunTimeline, type TimelineItem } from '@/components/forge/RunTimeline'
import { Button } from '@/components/ui/button'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import {
  buildMockRunAfterHitl,
  buildMockRunTimeline,
  playMockTimeline,
  type MockRunHandle,
} from '@/ws/mock'
import { handleForgeWsEvent } from './forge-events'

function mid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

export function ForgePage() {
  const t = useT()
  const { gameId: routeGameId } = useParams()
  const navigate = useNavigate()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)

  const [gameId, setGameId] = useState(routeGameId)
  const [input, setInput] = useState('做一个带计分的霓虹贪吃蛇，方向键控制，失败一键重开。')
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      id: 'm0',
      role: 'assistant',
      content: '工坊已就绪。描述玩法后我会创建 run，走 plan → HITL → art → code → qa（MSW + WS mock）。',
    },
  ])
  const [phase, setPhase] = useState<RunPhase | 'idle' | 'paused'>('idle')
  const [items, setItems] = useState<TimelineItem[]>([])
  const [hitl, setHitl] = useState<HitlWaitPayload | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [sideTab, setSideTab] = useState<'log' | 'play'>('log')
  const [runId, setRunId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const handleRef = useRef<MockRunHandle | null>(null)

  const detail = useQuery({
    queryKey: ['game', gameId],
    enabled: Boolean(gameId && token),
    queryFn: () => gamesApi.get(gameId!, token!),
  })

  const title = useMemo(() => {
    if (detail.data?.title) return detail.data.title
    if (gameId) return `编辑 ${gameId}`
    return '新建游戏'
  }, [detail.data?.title, gameId])

  useEffect(() => setGameId(routeGameId), [routeGameId])
  useEffect(() => () => handleRef.current?.cancel(), [])

  function pushItem(partial: Omit<TimelineItem, 'id' | 'at'> & { at?: string }) {
    setItems((prev) =>
      [
        { id: mid('ev'), at: partial.at ?? new Date().toISOString(), ...partial },
        ...prev,
      ].slice(0, 80),
    )
  }

  function eventBridge(activeGameId = gameId) {
    return {
      setPhase,
      pushItem,
      setHitl,
      setBusy,
      setPreviewUrl,
      setSideTab,
      appendMessages: (msgs: ChatMsg[]) => setMessages((m) => [...m, ...msgs]),
      gameId: activeGameId,
    }
  }

  async function startGeneration(requirement: string) {
    if (!token || !user) return
    if (!user.email_verified) {
      setErr('邮箱未验证，不能发起 generation_run')
      return
    }
    setErr(null)
    setBusy(true)
    setHitl(null)
    setPreviewUrl(null)
    setSideTab('log')
    handleRef.current?.cancel()

    try {
      let gid = gameId
      let gameTitle = detail.data?.title ?? '未命名游戏'
      if (!gid) {
        const created = await gamesApi.create(requirement.slice(0, 24) || '新游戏', requirement, token)
        gid = created.game_id
        gameTitle = requirement.slice(0, 24) || '新游戏'
        setGameId(gid)
        navigate(`/forge/${gid}`, { replace: true })
      }
      const run = await gamesApi.startRun(gid, requirement, token)
      setRunId(run.run_id)
      setPhase(RunPhase.plan)
      setMessages((m) => [
        ...m,
        { id: mid('m'), role: 'system', content: `run ${run.run_id} · mock WS 已连接` },
      ])
      handleRef.current = playMockTimeline(
        buildMockRunTimeline(run.run_id, gid, gameTitle),
        run.run_id,
        (ev) => handleForgeWsEvent(ev, eventBridge(gid)),
      )
    } catch (e) {
      setBusy(false)
      setPhase('idle')
      const msg = e instanceof ApiError ? e.message : '发起失败'
      setErr(msg)
      setMessages((m) => [...m, { id: mid('m'), role: 'assistant', content: `失败：${msg}` }])
    }
  }

  function onSend() {
    const text = input.trim()
    if (!text || busy) return
    setMessages((m) => [...m, { id: mid('m'), role: 'user', content: text }])
    setInput('')
    void startGeneration(text)
  }

  async function onApproveHitl(doc: HitlWaitPayload['design_doc']) {
    if (!runId || !gameId || !token || !hitl) return
    setBusy(true)
    try {
      await gamesApi.resolveHitl(
        gameId,
        runId,
        { node: hitl.node, decision: 'approve', modify_text: doc.gameplay },
        token,
      )
      setHitl(null)
      setPhase(RunPhase.art)
      setMessages((m) => [
        ...m,
        {
          id: mid('m'),
          role: 'assistant',
          content: `已批准策划稿，继续生成。（玩法摘要：${doc.gameplay.slice(0, 48)}…）`,
        },
      ])
      pushItem({ label: 'hitl_resolve · approved', detail: doc.title, tone: 'ok' })
      handleRef.current = playMockTimeline(buildMockRunAfterHitl(runId, gameId), runId, (ev) =>
        handleForgeWsEvent(ev, eventBridge(gameId)),
      )
    } catch (e) {
      setBusy(false)
      setErr(e instanceof ApiError ? e.message : 'HITL 解决失败')
    }
  }

  function onRejectHitl() {
    setHitl(null)
    setBusy(false)
    setPhase('idle')
    pushItem({ label: 'hitl_resolve · rejected', tone: 'err' })
    setMessages((m) => [
      ...m,
      { id: mid('m'), role: 'assistant', content: '已停止本次 run。可修改需求后重新发送。' },
    ])
  }

  return (
    <div className="flex h-[calc(100vh-7.5rem)] min-h-[560px] flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg tracking-tight text-white/95 md:text-xl">{t('forge')}</h1>
            <span className="rounded-md bg-white/[0.06] px-2 py-0.5 font-mono text-[10px] tracking-wider text-white/45 uppercase">
              console
            </span>
          </div>
          <p className="mt-0.5 text-sm text-white/40">
            {title}
            {runId ? <span className="ml-2 font-mono text-[11px] text-teal-400/60">{runId}</span> : null}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!user?.email_verified ? (
            <Link
              to="/settings"
              className="rounded-lg bg-amber-400/15 px-3 py-1.5 text-xs text-amber-100 ring-1 ring-amber-400/25"
            >
              邮箱未验证 → 去设置
            </Link>
          ) : null}
          <Link to="/games">
            <Button variant="ghost" className="!rounded-lg !px-3 !py-1.5 text-xs text-white/60">
              我的游戏
            </Button>
          </Link>
          <Link to="/forge">
            <Button
              variant="ghost"
              className="!rounded-lg !px-3 !py-1.5 text-xs text-teal-200/80 ring-1 ring-teal-400/20"
            >
              <Rocket className="h-3.5 w-3.5" />
              新游戏
            </Button>
          </Link>
        </div>
      </div>

      {err ? (
        <p role="alert" className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-200 ring-1 ring-red-400/25">
          {err}
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[1.05fr_1fr_0.95fr]">
        <ChatPanel
          messages={messages}
          input={input}
          onInputChange={setInput}
          onSend={onSend}
          disabled={busy}
        />
        <div className="flex min-h-0 flex-col gap-3">
          <div className="min-h-0 flex-1">
            <RunTimeline phase={phase} items={items} />
          </div>
          {hitl ? (
            <HitlCard payload={hitl} onApprove={onApproveHitl} onReject={onRejectHitl} busy={busy} />
          ) : busy ? (
            <div className="flex items-center gap-2 rounded-2xl border border-white/[0.06] bg-[#12151a] px-4 py-3 text-sm text-white/50">
              <Loader2 className="h-4 w-4 animate-spin text-teal-300" />
              管线运行中…
            </div>
          ) : null}
        </div>
        <ForgeSidePanel
          tab={sideTab}
          onTabChange={setSideTab}
          items={items}
          previewUrl={previewUrl}
          gameTitle={title}
        />
      </div>
    </div>
  )
}
