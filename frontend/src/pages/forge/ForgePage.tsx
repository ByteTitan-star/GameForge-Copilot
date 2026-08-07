import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bug,
  ChevronLeft,
  ChevronRight,
  Command,
  Gamepad2,
  Loader2,
  Maximize2,
  PanelRight,
  Pause,
  Play,
  Rocket,
  Send,
  Sparkles,
  Square,
  Upload,
} from 'lucide-react'
import { gamesApi } from '@/api/games'
import { RunPhase, RunStatus } from '@/api/enums'
import { formatApiError } from '@/api/error-message'
import type { HitlWaitPayload } from '@/api/ws-types'
import { ChatPanel, type ChatMsg } from '@/components/forge/ChatPanel'
import { HitlCard } from '@/components/forge/HitlCard'
import { RunTimeline, type TimelineItem } from '@/components/forge/RunTimeline'
import { GamePlayer } from '@/components/game/GamePlayer'
import { PublishNoteModal } from '@/components/games/PublishNoteModal'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'
import { isTrialUser } from '@/lib/trial'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { useLocaleStore } from '@/stores/locale-store'
import { connectRunWs, type RunWsHandle } from '@/ws/client'
import { handleForgeWsEvent } from './forge-events'
import { buildResumeHitl, pickActiveRun, previewFromGameDetail } from './resume'

function mid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

export function ForgePage() {
  const t = useT()
  const { gameId: routeGameId } = useParams()
  const navigate = useNavigate()
  const token = useAuthStore((s) => s.access_token)
  const user = useAuthStore((s) => s.user)
  const trial = isTrialUser(user)
  const locale = useLocaleStore((s) => s.locale)

  const [gameId, setGameId] = useState(routeGameId)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMsg[]>(() => [
    {
      id: 'm0',
      role: 'assistant',
      content: t('forgeWelcome'),
    },
  ])
  const [phase, setPhase] = useState<RunPhase | 'idle' | 'paused'>('idle')
  const [items, setItems] = useState<TimelineItem[]>([])
  const [hitl, setHitl] = useState<HitlWaitPayload | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [sideTab, setSideTab] = useState<'log' | 'play'>('log')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerTab, setDrawerTab] = useState<'chat' | 'run'>('chat')
  const [runId, setRunId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<RunStatus | 'idle'>('idle')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [publishing, setPublishing] = useState(false)
  const [publishOpen, setPublishOpen] = useState(false)
  const [quotaHint, setQuotaHint] = useState<string | null>(null)
  const handleRef = useRef<RunWsHandle | null>(null)
  const resumedRef = useRef<string | null>(null)
  const stageRef = useRef<HTMLElement | null>(null)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)

  const detail = useQuery({
    queryKey: ['game', gameId],
    enabled: Boolean(gameId && token),
    queryFn: () => gamesApi.get(gameId!, token!),
  })

  const title = useMemo(() => {
    if (detail.data?.title) return detail.data.title
    if (gameId) return `${t('editGame')} ${gameId}`
    return t('newGame')
  }, [detail.data?.title, gameId, locale])

  useEffect(() => {
    setGameId(routeGameId)
    resumedRef.current = null
  }, [routeGameId])
  useEffect(() => {
    setMessages((current) =>
      current.map((message) =>
        message.id === 'm0' ? { ...message, content: t('forgeWelcome') } : message,
      ),
    )
  }, [locale])
  useEffect(
    () => () => {
      const h = handleRef.current
      h?.close()
    },
    [],
  )

  // 进入已有游戏：恢复未结束 run + 重连 WS；有版本则挂草稿预览
  useEffect(() => {
    if (!gameId || !token) return
    if (resumedRef.current === gameId) return
    let cancelled = false

    async function resume() {
      try {
        const game = detail.data ?? (await gamesApi.get(gameId!, token!))
        if (cancelled) return
        const preview = previewFromGameDetail(game)
        if (preview && !previewUrl) {
          setPreviewUrl(preview)
          setSideTab('play')
        }

        // 试用账号：只挂预览，不恢复生成 / HITL
        if (isTrialUser(user)) {
          resumedRef.current = gameId!
          return
        }

        const listed = await gamesApi.listRuns(gameId!, token!)
        if (cancelled) return
        const active = pickActiveRun(listed.data)
        if (!active) {
          resumedRef.current = gameId!
          return
        }

        const run = await gamesApi.getRun(active.run_id, token!)
        if (cancelled) return
        setRunId(run.run_id)
        setRunStatus(run.status as RunStatus)
        const hitlPayload = buildResumeHitl(run, game.title)
        if (hitlPayload) {
          setHitl(hitlPayload)
          setPhase('paused')
          setBusy(false)
        } else {
          setPhase(run.phase)
          setBusy(run.status === 'running')
        }
        setMessages((m) => [
          ...m,
          { id: mid('m'), role: 'system', content: `${t('runResumed')} · ${run.run_id}` },
        ])
        pushItem({ label: t('runResumed'), detail: run.run_id, tone: 'info' })

        const prev = handleRef.current
        prev?.close()
        handleRef.current = connectRunWs({
          runId: run.run_id,
          accessToken: token!,
          onEvent: (ev) => handleForgeWsEvent(ev, eventBridge(gameId!)),
          onError: () => setErr(t('generationFailed')),
        })
        resumedRef.current = gameId!
      } catch {
        resumedRef.current = gameId!
      }
    }

    void resume()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅在 gameId/token/detail 就绪时恢复一次
  }, [gameId, token, detail.data?.game_id])
  useEffect(() => {
    if (!previewUrl) return
    setDrawerOpen(false)
  }, [previewUrl])
  useEffect(() => {
    if (!hitl) return
    setDrawerOpen(true)
    setDrawerTab('run')
  }, [hitl])
  useEffect(() => {
    function onShortcut(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const isTyping = target?.tagName === 'TEXTAREA' || target?.tagName === 'INPUT'
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        composerRef.current?.focus()
        return
      }
      if (!isTyping && event.code === 'Space') {
        event.preventDefault()
        composerRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onShortcut)
    return () => window.removeEventListener('keydown', onShortcut)
  }, [])

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
      setQuotaHint,
      gameId: activeGameId,
      t,
    }
  }

  function closeHandle() {
    handleRef.current?.close()
    handleRef.current = null
  }

  async function startGeneration(requirement: string) {
    if (!token || !user) return
    if (!user.email_verified) {
      setErr(t('emailRunError'))
      return
    }
    setErr(null)
    setBusy(true)
    setHitl(null)
    setPreviewUrl(null)
    setSideTab('log')
    closeHandle()

    try {
      let gid = gameId
      let gameTitle = detail.data?.title ?? t('unnamedGame')
      if (!gid) {
        const created = await gamesApi.create(requirement.slice(0, 24) || t('newGame'), requirement, token)
        gid = created.game_id
        gameTitle = requirement.slice(0, 24) || t('newGame')
        setGameId(gid)
        navigate(`/forge/${gid}`, { replace: true })
      }
      const run = await gamesApi.startRun(gid, requirement, token)
      setRunId(run.run_id)
      setRunStatus(RunStatus.running)
      setPhase(RunPhase.plan)
      setMessages((m) => [
        ...m,
        { id: mid('m'), role: 'system', content: `${t('runStarting')} · ${run.run_id}` },
      ])
      const onEvent = (ev: Parameters<typeof handleForgeWsEvent>[0]) =>
        handleForgeWsEvent(ev, eventBridge(gid))
      handleRef.current = connectRunWs({
        runId: run.run_id,
        accessToken: token,
        onEvent,
        onError: () => setErr(t('generationFailed')),
      })
    } catch (e) {
      setBusy(false)
      setPhase('idle')
      const msg = formatApiError(e, t('generationFailed'))
      setErr(msg)
      setMessages((m) => [...m, { id: mid('m'), role: 'assistant', content: `${t('generationFailed')}: ${msg}` }])
    }
  }

  function onSend() {
    const text = input.trim()
    if (!text || busy) return
    if (trial) {
      setErr(t('trialForgeLocked'))
      return
    }
    setMessages((m) => [...m, { id: mid('m'), role: 'user', content: text }])
    setInput('')
    setDrawerOpen(true)
    setDrawerTab('run')
    void startGeneration(text)
  }

  function reportBug() {
    if (trial) {
      setErr(t('trialForgeLocked'))
      return
    }
    setInput(t('bugPrompt'))
    setDrawerOpen(true)
    setDrawerTab('chat')
    window.setTimeout(() => composerRef.current?.focus(), 0)
  }

  function enterFullscreen() {
    if (!stageRef.current?.requestFullscreen) return
    void stageRef.current.requestFullscreen()
  }

  async function onApproveHitl(doc: HitlWaitPayload['design_doc']) {
    if (trial || !runId || !gameId || !token || !hitl) return
    setBusy(true)
    const modified =
      doc.gameplay !== hitl.design_doc.gameplay || doc.controls !== hitl.design_doc.controls
    try {
      await gamesApi.resolveHitl(
        gameId,
        runId,
        {
          node: hitl.node,
          decision: modified ? 'modify' : 'approve',
          modify_text: modified
            ? `gameplay: ${doc.gameplay}\ncontrols: ${doc.controls}`
            : null,
        },
        token,
      )
      setHitl(null)
      setPhase(RunPhase.art)
      setRunStatus(RunStatus.running)
      setMessages((m) => [
        ...m,
        {
          id: mid('m'),
          role: 'assistant',
          content: `${t('designApproved')} (${t('gameplay')}: ${doc.gameplay.slice(0, 48)}…)`,
        },
      ])
      pushItem({ label: t('hitlApproved'), detail: doc.title, tone: 'ok' })
      // real：继续复用已连接的 WS，后端 resume 后推事件
    } catch (e) {
      setBusy(false)
      setErr(formatApiError(e, t('generationFailed')))
    }
  }

  function onRejectHitl() {
    // 契约仅有 approve|modify（都会 resume）；拒绝 = 本地中止并断开 WS，不调 resolve
    setHitl(null)
    setBusy(false)
    setRunStatus('idle')
    setPhase('idle')
    closeHandle()
    pushItem({ label: t('hitlRejected'), tone: 'err' })
    setMessages((m) => [
      ...m,
      { id: mid('m'), role: 'assistant', content: t('runStopped') },
    ])
  }

  async function pauseRun() {
    if (!runId || !token || trial) return
    try {
      const resp = await gamesApi.pauseRun(runId, token)
      setRunStatus(resp.status as RunStatus)
      setPhase('paused')
      setBusy(false)
      pushItem({ label: '已暂停', detail: runId, tone: 'info' })
    } catch (e) {
      setErr(formatApiError(e, '暂停失败'))
    }
  }

  async function resumeRun() {
    if (!runId || !token || trial || hitl) return
    try {
      const resp = await gamesApi.resumeRun(runId, token)
      setRunStatus(resp.status as RunStatus)
      setPhase(resp.phase)
      setBusy(true)
      pushItem({ label: '已续跑', detail: runId, tone: 'info' })
      if (!handleRef.current) {
        handleRef.current = connectRunWs({
          runId,
          accessToken: token,
          onEvent: (ev) => handleForgeWsEvent(ev, eventBridge(gameId)),
          onError: () => setErr(t('generationFailed')),
        })
      }
    } catch (e) {
      setErr(formatApiError(e, '续跑失败'))
    }
  }

  async function cancelRun() {
    if (!runId || !token || trial) return
    try {
      const resp = await gamesApi.cancelRun(runId, token)
      setRunStatus(resp.status as RunStatus)
      setBusy(false)
      setPhase('idle')
      setHitl(null)
      closeHandle()
      pushItem({ label: '已取消', detail: runId, tone: 'err' })
    } catch (e) {
      setErr(formatApiError(e, '取消失败'))
    }
  }

  const canPause = Boolean(runId && runStatus === RunStatus.running && !hitl && !trial)
  const canResume = Boolean(runId && runStatus === RunStatus.paused && !hitl && !trial)
  const canCancel = Boolean(
    runId && (runStatus === RunStatus.running || runStatus === RunStatus.paused) && !trial,
  )

  async function submitPublish(note: string) {
    if (trial) {
      setErr(t('trialGamesHint'))
      return
    }
    if (!gameId || !token || !detail.data) return
    if (detail.data.current_version < 1) {
      setErr(t('generationFailed'))
      return
    }
    setPublishing(true)
    setErr(null)
    try {
      await gamesApi.submitPublish(gameId, detail.data.current_version, note || '从设计页提交', token)
      await detail.refetch()
      setPublishOpen(false)
      setMessages((m) => [
        ...m,
        { id: mid('m'), role: 'system', content: '已提交发布审批' },
      ])
    } catch (e) {
      setErr(formatApiError(e, '提交发布失败'))
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="forge-page flex h-[calc(100vh-2.5rem)] min-h-[620px] flex-col gap-3 md:h-[calc(100vh-3.5rem)]">
      <header className="forge-topbar flex shrink-0 items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="forge-eyebrow">{t('forge')}</span>
            <span className="forge-live-dot" aria-hidden />
            <span className="font-mono text-[10px] tracking-[0.14em] text-[#6c747c] uppercase">
              {previewUrl ? t('playable') : busy ? t('building') : t('ready')}
            </span>
            {quotaHint ? (
              <span className="hidden font-mono text-[10px] text-[#8a939c] md:inline">{quotaHint}</span>
            ) : null}
          </div>
          <h1 className="mt-1 truncate text-base font-medium tracking-tight text-[#1d2329] md:text-lg">{title}</h1>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {!user?.email_verified ? (
            <Link
              to="/settings"
              className="hidden rounded-lg bg-[#ffcf5a]/20 px-2.5 py-1.5 text-[11px] text-[#785d14] ring-1 ring-[#d49d12]/20 sm:block"
            >
              {t('emailUnverified')}
            </Link>
          ) : null}
          <button
            type="button"
            title={t('captureIssue')}
            aria-label={t('captureIssue')}
            onClick={reportBug}
            className="grid h-9 w-9 cursor-pointer place-items-center rounded-lg border border-[#ff705c]/25 bg-[#ff705c]/10 text-[#b64235] transition hover:border-[#ff705c]/45 hover:bg-[#ff705c]/20 hover:text-[#8e2f26]"
          >
            <Bug className="h-4 w-4" />
          </button>
          {canPause ? (
            <Button
              variant="ghost"
              className="!h-9 !rounded-lg !px-2.5 text-xs !text-[#59636c]"
              onClick={() => void pauseRun()}
            >
              <Pause className="h-3.5 w-3.5" />
              暂停
            </Button>
          ) : null}
          {canResume ? (
            <Button
              variant="ghost"
              className="!h-9 !rounded-lg !px-2.5 text-xs !text-[#1b8b6c]"
              onClick={() => void resumeRun()}
            >
              <Play className="h-3.5 w-3.5" />
              续跑
            </Button>
          ) : null}
          {canCancel ? (
            <Button
              variant="ghost"
              className="!h-9 !rounded-lg !px-2.5 text-xs !text-[#b64235]"
              onClick={() => void cancelRun()}
            >
              <Square className="h-3.5 w-3.5" />
              取消
            </Button>
          ) : null}
          {gameId && !trial && detail.data && detail.data.current_version >= 1 ? (
            <Button
              variant="ghost"
              className="!h-9 !rounded-lg !px-3 text-xs !text-[#59636c] hover:!bg-black/[0.05] hover:!text-[#1d2329]"
              disabled={publishing || busy}
              onClick={() => setPublishOpen(true)}
            >
              {publishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              提交发布
            </Button>
          ) : null}
          <Link to="/games" className="hidden sm:block">
            <Button variant="ghost" className="!h-9 !rounded-lg !px-3 text-xs !text-[#59636c] hover:!bg-black/[0.05] hover:!text-[#1d2329]">
              <Gamepad2 className="h-3.5 w-3.5" />
              {t('games')}
            </Button>
          </Link>
          {trial ? null : (
            <Link to="/forge">
              <Button variant="ghost" className="!h-9 !rounded-lg !bg-[#20262d] !px-3 text-xs !text-white ring-1 ring-[#20262d] hover:!bg-[#303942]">
                <Rocket className="h-3.5 w-3.5" />
                {t('newGame')}
              </Button>
            </Link>
          )}
        </div>
      </header>

      {err ? (
        <p role="alert" className="shrink-0 rounded-lg border border-[#d84d3e]/25 bg-[#ff705c]/10 px-3 py-2 text-sm text-[#8e2f26]">
          {err}
        </p>
      ) : null}

      <div className="relative flex min-h-0 flex-1 gap-3">
        <section ref={stageRef} className="forge-stage relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-[20px] border border-black/[0.1] bg-[#f4f6f7]">
          <div className="forge-stage-grid" aria-hidden />
          <div className="relative flex min-h-0 flex-1 flex-col">
            <div className="flex shrink-0 items-center justify-between px-4 py-3 md:px-5">
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-black/10 bg-white/75 px-2 py-1 font-mono text-[10px] tracking-[0.14em] text-[#6b747d] uppercase">
                  {previewUrl ? t('playView') : t('previewStage')}
                </span>
                {sideTab === 'play' && previewUrl ? <span className="text-[11px] text-[#1b8b6c]">{t('versionReady')}</span> : null}
              </div>
              <div className="flex items-center gap-1">
                {previewUrl ? (
                  <button
                    type="button"
                    title={t('fullscreenPlay')}
                    aria-label={t('fullscreenPlay')}
                    onClick={enterFullscreen}
                    className="grid h-8 w-8 cursor-pointer place-items-center rounded-md text-[#707981] transition hover:bg-black/[0.06] hover:text-[#1d2329]"
                  >
                    <Maximize2 className="h-3.5 w-3.5" />
                  </button>
                ) : null}
                <button
                  type="button"
                  title={drawerOpen ? t('collapseWorkbench') : t('openWorkbench')}
                  aria-label={drawerOpen ? t('collapseWorkbench') : t('openWorkbench')}
                  onClick={() => setDrawerOpen((open) => !open)}
                  className="grid h-8 w-8 cursor-pointer place-items-center rounded-md text-[#707981] transition hover:bg-black/[0.06] hover:text-[#1d2329]"
                >
                  <PanelRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div className="min-h-0 flex-1 px-3 pb-3 md:px-4 md:pb-4">
              {previewUrl ? (
                <GamePlayer
                  src={previewUrl}
                  title={title}
                  variant="stage"
                  accessToken={token}
                />
              ) : (
                <div className="forge-empty-state grid h-full place-items-center px-6 pb-24 text-center">
                  <div className="max-w-xl">
                    <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-[#ff705c]/25 bg-[#ff705c]/10 text-[#d84d3e] shadow-[0_0_35px_rgba(255,112,92,0.12)]">
                      <Sparkles className="h-6 w-6" />
                    </div>
                    <p className="mt-6 font-mono text-[10px] tracking-[0.24em] text-[#d84d3e] uppercase">{t('gameForgeLabel')}</p>
                    <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-[#1d2329] md:text-5xl">{t('forgeHeroTitle')}</h2>
                    <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-[#68727b] md:text-base">{t('forgeHeroSubtitle')}</p>
                    {trial ? (
                      <p className="mx-auto mt-6 max-w-md text-sm text-[#8a6b21]">{t('trialForgeLocked')}</p>
                    ) : (
                      <div className="mt-7 flex flex-wrap justify-center gap-2">
                        {[t('retroShooter'), t('coopAdventure'), t('cozyCollection')].map((suggestion) => (
                          <button
                            key={suggestion}
                            type="button"
                            onClick={() => {
                              setInput(`${t('suggestionPrefix')}${suggestion}${t('suggestionSuffix')}`)
                              composerRef.current?.focus()
                            }}
                            className="cursor-pointer rounded-full border border-black/10 bg-white/70 px-3 py-1.5 text-xs text-[#65707a] transition hover:border-[#ff705c]/35 hover:bg-[#ff705c]/10 hover:text-[#9b382e]"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="relative z-10 shrink-0 px-3 pb-3 md:px-6 md:pb-5">
              {trial ? (
                <p className="mx-auto mb-2 max-w-3xl text-center text-xs text-[#8a6b21]">{t('trialForgeLocked')}</p>
              ) : null}
              <form
                className="forge-composer mx-auto max-w-3xl rounded-2xl border border-black/[0.1] bg-white/90 p-2 shadow-[0_16px_50px_rgba(38,48,56,0.14)] backdrop-blur-xl"
                onSubmit={(event) => {
                  event.preventDefault()
                  onSend()
                }}
              >
                <label htmlFor="forge-composer" className="sr-only">
                  {previewUrl ? t('describeIteration') : t('describeNewGame')}
                </label>
                <div className="flex items-end gap-2">
                  <textarea
                    id="forge-composer"
                    ref={composerRef}
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    rows={1}
                    disabled={busy || trial}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault()
                        onSend()
                      }
                    }}
                    className="min-h-10 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm leading-5 text-[#1d2329] outline-none placeholder:text-[#8d969e] disabled:opacity-50"
                    placeholder={previewUrl ? t('describeIteration') : t('describeNewGame')}
                  />
                  <button
                    type="submit"
                    disabled={busy || trial || !input.trim()}
                    aria-label={t('sendRequirement')}
                    className="grid h-10 w-10 shrink-0 cursor-pointer place-items-center rounded-xl bg-[#ff705c] text-white transition hover:bg-[#ff8877] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  </button>
                </div>
                <div className="flex items-center justify-between px-3 pb-1 pt-0.5">
                  <span className="font-mono text-[10px] tracking-[0.16em] text-[#9aa2a9]">{previewUrl ? t('edit') : t('create')}</span>
                  {busy ? <span className="text-[10px] text-[#7b858e]">{t('buildingPlayable')}</span> : null}
                </div>
              </form>
            </div>
          </div>
        </section>

        <aside
          className={cn(
            'forge-drawer relative z-20 flex h-full shrink-0 flex-col overflow-hidden rounded-[18px] border border-black/[0.1] bg-[#f8fafb]/95 shadow-2xl backdrop-blur-xl transition-[width] duration-300 ease-out max-lg:absolute max-lg:right-0 max-lg:top-0',
            drawerOpen
              ? 'w-[min(92vw,380px)]'
              : 'w-12 max-lg:pointer-events-none max-lg:w-0 max-lg:border-0 max-lg:bg-transparent max-lg:shadow-none',
          )}
        >
          {drawerOpen ? (
            <>
              <header className="flex shrink-0 items-center justify-between border-b border-black/[0.07] px-3 py-3">
                <div className="flex items-center gap-2">
                  <div className="grid h-7 w-7 place-items-center rounded-lg bg-[#20262d] text-white/80">
                    <PanelRight className="h-3.5 w-3.5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[#20262d]">{t('workbench')}</p>
                  </div>
                </div>
                <button
                  type="button"
                  title={t('collapseWorkbench')}
                  aria-label={t('collapseWorkbench')}
                  onClick={() => setDrawerOpen(false)}
                  className="grid h-8 w-8 cursor-pointer place-items-center rounded-md text-[#737d85] transition hover:bg-black/[0.06] hover:text-[#20262d]"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </header>
              <div className="flex shrink-0 gap-1 border-b border-black/[0.07] p-2">
                {([
                  ['chat', t('chat')],
                  ['run', t('run')],
                ] as const).map(([tab, label]) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setDrawerTab(tab)}
                    className={cn(
                      'flex-1 cursor-pointer rounded-lg px-3 py-2 text-xs transition',
                      drawerTab === tab ? 'bg-[#20262d] text-white' : 'text-[#7b858e] hover:bg-black/[0.05] hover:text-[#20262d]',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="min-h-0 flex-1">
                {drawerTab === 'chat' ? (
                  <ChatPanel
                    messages={messages}
                    input={input}
                    onInputChange={setInput}
                    onSend={onSend}
                    disabled={busy}
                    streaming={busy && !hitl}
                    showComposer={false}
                    className="!rounded-none !border-0 !bg-transparent"
                  />
                ) : (
                  <div className="flex h-full min-h-0 flex-col gap-2 p-2">
                    <RunTimeline phase={phase} items={items} className="min-h-0 flex-1 !rounded-xl !border-black/[0.08] !bg-white/50" />
                    {hitl ? (
                      <HitlCard
                        payload={hitl}
                        onApprove={onApproveHitl}
                        onReject={onRejectHitl}
                        busy={busy || trial}
                      />
                    ) : busy ? (
                      <div className="flex shrink-0 items-center gap-2 rounded-xl border border-black/[0.08] bg-white/70 px-3 py-2.5 text-xs text-[#68727b]">
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-[#ff705c]" />
                        {t('buildingPlayable')}
                      </div>
                    ) : (
                      <div className="flex shrink-0 items-center gap-2 rounded-xl border border-black/[0.08] bg-white/70 px-3 py-2.5 text-xs text-[#7d8790]">
                        <span className={cn('forge-status-dot', sideTab === 'play' && 'is-ready')} />
                        {sideTab === 'play' ? t('playReady') : t('waitingNextRun')}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex h-full flex-col items-center justify-between py-3">
              <button
                type="button"
                title={t('openWorkbench')}
                aria-label={t('openWorkbench')}
                onClick={() => setDrawerOpen(true)}
                className="grid h-8 w-8 cursor-pointer place-items-center rounded-md text-[#737d85] transition hover:bg-black/[0.06] hover:text-[#20262d]"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <div className="flex flex-col items-center gap-3">
                <span className="forge-rail-label">{t('workbench')}</span>
                <span className={cn('forge-status-dot', sideTab === 'play' && 'is-ready')} />
              </div>
              <Command className="h-3.5 w-3.5 text-[#98a0a7]" />
            </div>
          )}
        </aside>
      </div>

      <PublishNoteModal
        open={publishOpen}
        gameTitle={title}
        defaultNote=""
        busy={publishing}
        onCancel={() => setPublishOpen(false)}
        onConfirm={(note) => void submitPublish(note)}
      />
    </div>
  )
}
