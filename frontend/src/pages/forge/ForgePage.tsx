import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bug,
  ChevronLeft,
  Loader2,
  Maximize2,
  Pause,
  Play,
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
  const [, setSideTab] = useState<'log' | 'play'>('log')
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
      if (!gid) {
        const created = await gamesApi.create(requirement.slice(0, 24) || t('newGame'), requirement, token)
        gid = created.game_id
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
    void startGeneration(text)
  }

  function reportBug() {
    if (trial) {
      setErr(t('trialForgeLocked'))
      return
    }
    setInput(t('bugPrompt'))
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
      pushItem({ label: t('runPaused'), detail: runId, tone: 'info' })
    } catch (e) {
      setErr(formatApiError(e, t('pauseFailed')))
    }
  }

  async function resumeRun() {
    if (!runId || !token || trial || hitl) return
    try {
      const resp = await gamesApi.resumeRun(runId, token)
      setRunStatus(resp.status as RunStatus)
      setPhase(resp.phase)
      setBusy(true)
      pushItem({ label: t('runResumed'), detail: runId, tone: 'info' })
      if (!handleRef.current) {
        handleRef.current = connectRunWs({
          runId,
          accessToken: token,
          onEvent: (ev) => handleForgeWsEvent(ev, eventBridge(gameId)),
          onError: () => setErr(t('generationFailed')),
        })
      }
    } catch (e) {
      setErr(formatApiError(e, t('resumeFailed')))
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
      pushItem({ label: t('runCancelled'), detail: runId, tone: 'err' })
    } catch (e) {
      setErr(formatApiError(e, t('cancelFailed')))
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
      await gamesApi.submitPublish(gameId, detail.data.current_version, note || t('publishFromForge'), token)
      await detail.refetch()
      setPublishOpen(false)
      setMessages((m) => [
        ...m,
        { id: mid('m'), role: 'system', content: t('publishSubmittedMsg') },
      ])
    } catch (e) {
      setErr(formatApiError(e, t('submitPublishFailed')))
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <header className="gf-glass flex shrink-0 flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
          <Link
            to="/games"
            className="gf-interactive inline-flex items-center gap-1 gf-page-muted transition hover:text-[var(--gf-primary)]"
          >
            <ChevronLeft className="h-4 w-4" />
            {t('backToGames')}
          </Link>
          <span className="gf-page-muted opacity-40">/</span>
          <span className="gf-page-body">{t('forge')}</span>
          <span className="hidden gf-page-muted opacity-40 sm:inline">·</span>
          <span className="truncate font-medium gf-page-body">{title}</span>
          <span className="gf-bg-accent-soft gf-text-accent rounded-md px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider">
            {previewUrl ? t('playable') : busy ? t('building') : t('ready')}
          </span>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-1.5">
          {!user?.email_verified ? (
            <Link
              to="/settings"
              className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-900 ring-1 ring-amber-200"
            >
              {t('emailUnverified')}
            </Link>
          ) : null}
          {quotaHint ? (
            <span className="hidden font-mono text-[10px] gf-page-muted md:inline">{quotaHint}</span>
          ) : null}
          <button
            type="button"
            title={t('captureIssue')}
            aria-label={t('captureIssue')}
            onClick={reportBug}
            disabled={trial}
            className="gf-interactive gf-border-subtle grid h-9 w-9 cursor-pointer place-items-center rounded-lg border bg-black/[0.03] gf-page-muted transition hover:border-[rgba(var(--gf-primary-rgb),0.3)] hover:text-[var(--gf-primary)] disabled:opacity-40"
          >
            <Bug className="h-4 w-4" />
          </button>
          {canPause ? (
            <Button variant="ghost" className="!h-9 !rounded-lg !px-2.5 text-xs !text-[var(--gf-text)]" onClick={() => void pauseRun()}>
              <Pause className="h-3.5 w-3.5" />
              {t('pauseRun')}
            </Button>
          ) : null}
          {canResume ? (
            <Button variant="ghost" className="gf-text-accent !h-9 !rounded-lg !px-2.5 text-xs" onClick={() => void resumeRun()}>
              <Play className="h-3.5 w-3.5" />
              {t('resumeRunBtn')}
            </Button>
          ) : null}
          {canCancel ? (
            <Button variant="ghost" className="!h-9 !rounded-lg !px-2.5 text-xs !text-rose-600" onClick={() => void cancelRun()}>
              <Square className="h-3.5 w-3.5" />
              {t('cancelRunBtn')}
            </Button>
          ) : null}
          {gameId && !trial && detail.data && detail.data.current_version >= 1 ? (
            <Button
              variant="ghost"
              className="!h-9 !rounded-lg !px-3 text-xs !text-[var(--gf-text)]"
              disabled={publishing || busy}
              onClick={() => setPublishOpen(true)}
            >
              {publishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              {t('submitPublishBtn')}
            </Button>
          ) : null}
        </div>
      </header>

      {err ? (
        <p role="alert" className="shrink-0 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {err}
        </p>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        {/* 左：需求对话 + 生成进度 — 35% */}
        <section className="gf-glass flex min-h-[420px] w-full shrink-0 flex-col overflow-hidden rounded-xl lg:w-[35%] lg:min-w-[300px] lg:max-w-[420px]">
          <div className="min-h-0 flex-1">
            <ChatPanel
              variant="workshop"
              messages={messages}
              input={input}
              onInputChange={setInput}
              onSend={onSend}
              disabled={busy || trial}
              streaming={busy && !hitl}
              showComposer={!trial}
              placeholder={previewUrl ? t('describeIteration') : t('describeNewGame')}
              className="h-full !rounded-none !border-0 !bg-transparent"
            />
          </div>

          {(items.length > 0 || hitl || busy) ? (
            <div className="shrink-0 space-y-2 border-t gf-border-subtle border p-3">
              <p className="font-mono text-[10px] tracking-[0.14em] gf-page-muted uppercase">{t('generationFlow')}</p>
              <RunTimeline
                phase={phase}
                items={items}
                className="max-h-36 !rounded-xl !gf-border-subtle border !bg-white/[0.03]"
              />
              {hitl ? (
                <HitlCard
                  payload={hitl}
                  onApprove={onApproveHitl}
                  onReject={onRejectHitl}
                  busy={busy || trial}
                />
              ) : null}
            </div>
          ) : null}

          {!trial ? (
            <div className="shrink-0 border-t gf-border-subtle border px-3 py-3">
              <p className="mb-2 font-mono text-[10px] tracking-[0.12em] gf-page-muted uppercase">{t('quickTemplates')}</p>
              <div className="flex flex-wrap gap-2">
                {[t('retroShooter'), t('coopAdventure'), t('cozyCollection')].map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setInput(`${t('suggestionPrefix')}${suggestion}${t('suggestionSuffix')}`)}
                    className="gf-interactive cursor-pointer rounded-full border gf-border-subtle border bg-black/[0.03] px-3 py-1.5 text-xs gf-page-muted transition hover:border-[rgba(var(--gf-primary-rgb),0.35)] hover:text-[var(--gf-primary)]"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <p className="gf-banner-warn shrink-0 border-t gf-border-subtle border px-3 py-3 text-xs">{t('trialForgeLocked')}</p>
          )}
        </section>

        {/* 右：预览舞台 — 65% */}
        <section
          ref={stageRef}
          className="gf-glass flex min-h-[420px] min-w-0 flex-1 flex-col overflow-hidden rounded-xl"
        >
          <div className="flex shrink-0 items-center justify-between border-b gf-border-subtle border px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="gf-text-accent font-mono text-[10px] tracking-[0.14em] opacity-80 uppercase">
                {previewUrl ? t('playView') : t('previewStage')}
              </span>
              {previewUrl ? (
                <span className="text-[11px] text-emerald-300">{t('versionReady')}</span>
              ) : null}
            </div>
            {previewUrl ? (
              <button
                type="button"
                title={t('fullscreenPlay')}
                aria-label={t('fullscreenPlay')}
                onClick={enterFullscreen}
                className="gf-page-muted grid h-8 w-8 cursor-pointer place-items-center rounded-lg transition hover:bg-black/[0.04] hover:text-[var(--gf-text)]"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </div>

          <div className="min-h-0 flex-1 p-3 md:p-4">
            {previewUrl ? (
              <GamePlayer src={previewUrl} title={title} variant="stage" accessToken={token} />
            ) : (
              <div className="grid h-full min-h-[280px] place-items-center px-6 text-center">
                <div className="max-w-md">
                  <div className="gf-empty-icon-wrap mx-auto grid h-16 w-16 place-items-center rounded-2xl border">
                    <Sparkles className="gf-text-accent h-7 w-7" />
                  </div>
                  <h2 className="mt-6 text-2xl font-semibold gf-page-body md:text-3xl">{t('forgeHeroTitle')}</h2>
                  <p className="mt-3 text-sm leading-relaxed gf-page-muted">{t('forgeHeroSubtitle')}</p>
                </div>
              </div>
            )}
          </div>
        </section>
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
