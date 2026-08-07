import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bug,
  Box,
  ChevronLeft,
  Loader2,
  Maximize2,
  PanelRightClose,
  PanelRightOpen,
  Pause,
  Play,
  Square,
  Upload,
} from 'lucide-react'
import { gamesApi } from '@/api/games'
import { RunPhase, RunStatus } from '@/api/enums'
import { formatApiError } from '@/api/error-message'
import type { HitlWaitPayload } from '@/api/ws-types'
import { ChatPanel, type ChatMsg } from '@/components/forge/ChatPanel'
import { FailureRecoveryBar } from '@/components/forge/FailureRecoveryBar'
import { ForgeAiStatusBar } from '@/components/forge/ForgeAiStatusBar'
import { ForgeQuickTemplates } from '@/components/forge/ForgeQuickTemplates'
import { ForgeSplitLayout } from '@/components/forge/ForgeSplitLayout'
import { HitlCard } from '@/components/forge/HitlCard'
import { LlmConfigSelect } from '@/components/forge/LlmConfigSelect'
import { RunHistoryPanel } from '@/components/forge/RunHistoryPanel'
import { RunTimeline, type TimelineItem } from '@/components/forge/RunTimeline'
import { StagePipeline } from '@/components/forge/StagePipeline'
import { TemplatePicker } from '@/components/forge/TemplatePicker'
import { VersionTimeline } from '@/components/forge/VersionTimeline'
import { GamePlayer } from '@/components/game/GamePlayer'
import { PublishNoteModal } from '@/components/games/PublishNoteModal'
import { Button } from '@/components/ui/button'
import { isFailureHitlNode } from '@/lib/hitl-design-doc'
import { isTrialUser } from '@/lib/trial'
import {
  applyPhaseStart,
  emptyStagePipeline,
  type StagePipelineState,
} from '@/lib/stage-pipeline-state'
import { useT } from '@/i18n/use-t'
import { useAuthStore } from '@/stores/auth-store'
import { useLocaleStore } from '@/stores/locale-store'
import { connectRunWs, type RunWsHandle } from '@/ws/client'
import { handleForgeWsEvent } from './forge-events'
import { buildResumeHitl, pickActiveRun, previewFromGameDetail } from './resume'
import { draftArtifactUrl } from '@/lib/hosting'
import { getTemplateById } from '@/constants/templates'
import { templatesApi, type GameTemplate } from '@/api/templates'
import type { RunListItem } from '@/api/types'
import { cn } from '@/lib/cn'

function mid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

export function ForgePage() {
  const t = useT()
  const { gameId: routeGameId } = useParams()
  const [searchParams] = useSearchParams()
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
  const [previewVersion, setPreviewVersion] = useState<number | null>(null)
  const [quotaHint, setQuotaHint] = useState<string | null>(null)
  const [llmConfigId, setLlmConfigId] = useState<string | null>(null)
  const [currentModel, setCurrentModel] = useState<string | null>(null)
  const [rightTab, setRightTab] = useState<'preview' | 'versions' | 'runs'>('preview')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [runErrors, setRunErrors] = useState<Record<string, string>>({})
  const [reconnectingRunId, setReconnectingRunId] = useState<string | null>(null)
  const [flashRing, setFlashRing] = useState(false)
  const [stageOpen, setStageOpen] = useState(false)
  const [stagePipeline, setStagePipeline] = useState<StagePipelineState>(emptyStagePipeline)
  const [retryBusy, setRetryBusy] = useState(false)
  const handleRef = useRef<RunWsHandle | null>(null)
  const resumedRef = useRef<string | null>(null)
  const stageRef = useRef<HTMLElement | null>(null)
  const prevPreviewRef = useRef<string | null>(null)

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

  const latestVersion = useMemo(() => {
    const vers = detail.data?.versions ?? []
    if (vers.length === 0) return detail.data?.current_version ?? 0
    return Math.max(...vers.map((v) => v.version))
  }, [detail.data?.versions, detail.data?.current_version])

  const showFailureRecovery = Boolean(
    !trial &&
      runId &&
      (runStatus === RunStatus.failed || (hitl != null && isFailureHitlNode(hitl.node))),
  )
  const failureSummary = runId ? runErrors[runId] : undefined

  useEffect(() => {
    const tplId = searchParams.get('template')
    if (!tplId || gameId) return
    void templatesApi.list().then((list) => {
      const tpl = list.find((t) => t.template_id === tplId) ?? null
      if (tpl) {
        setSelectedTemplateId(tpl.template_id)
        if (tpl.requirement_seed) setInput(tpl.requirement_seed)
        return
      }
      const legacy = getTemplateById(tplId)
      if (legacy) {
        setSelectedTemplateId(legacy.id)
        if (legacy.requirement_seed) setInput(legacy.requirement_seed)
      }
    })
  }, [searchParams, gameId])

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

  useEffect(() => {
    if (!previewUrl || previewUrl === prevPreviewRef.current) return
    prevPreviewRef.current = previewUrl
    setFlashRing(true)
    const timer = window.setTimeout(() => setFlashRing(false), 900)
    return () => window.clearTimeout(timer)
  }, [previewUrl])

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
          setPreviewVersion(game.current_version)
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
          setStageOpen(true)
        } else {
          setPhase(run.phase)
          setBusy(run.status === 'running')
          if (run.status === 'running' || run.status === 'paused') setStageOpen(true)
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
          onEvent: (ev) => handleForgeWsEvent(ev, eventBridge(gameId!, run.run_id)),
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

  function eventBridge(activeGameId = gameId, activeRunId: string | null = runId) {
    return {
      setPhase,
      pushItem,
      setHitl,
      setBusy,
      setPreviewUrl,
      setSideTab,
      appendMessages: (msgs: ChatMsg[]) => setMessages((m) => [...m, ...msgs]),
      setQuotaHint,
      setCurrentModel,
      setRunError: (rid: string, message: string) => {
        setRunErrors((prev) => ({ ...prev, [rid]: message }))
        setRunStatus(RunStatus.failed)
      },
      setStagePipeline,
      gameId: activeGameId,
      runId: activeRunId,
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
    setStagePipeline(applyPhaseStart(emptyStagePipeline(), RunPhase.plan))
    closeHandle()

    try {
      let gid = gameId
      if (!gid) {
        const created = await gamesApi.create(requirement.slice(0, 24) || t('newGame'), requirement, token)
        gid = created.game_id
        setGameId(gid)
        navigate(`/forge/${gid}`, { replace: true })
      }
      const run = await gamesApi.startRun(gid, requirement, token, llmConfigId)
      setRunId(run.run_id)
      setRunStatus(RunStatus.running)
      setPhase(RunPhase.plan)
      setMessages((m) => [
        ...m,
        { id: mid('m'), role: 'system', content: `${t('runStarting')} · ${run.run_id}` },
      ])
      const onEvent = (ev: Parameters<typeof handleForgeWsEvent>[0]) =>
        handleForgeWsEvent(ev, eventBridge(gid, run.run_id))
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
    setStageOpen(true)
    void startGeneration(text)
  }

  function onReviseRequirement() {
    setInput(t('failureReviseTemplate'))
  }

  async function retryFailedRun() {
    if (!runId || !token || trial) return
    setRetryBusy(true)
    setErr(null)
    try {
      const resp = await gamesApi.retryRun(runId, token)
      setRunStatus(resp.status as RunStatus)
      setPhase(resp.phase)
      setBusy(resp.status === RunStatus.running)
      setHitl(null)
      setRunErrors((prev) => {
        const next = { ...prev }
        delete next[runId]
        return next
      })
      pushItem({ label: t('failureRetry'), detail: runId, tone: 'info' })
      if (
        !handleRef.current &&
        (resp.status === RunStatus.running || resp.status === RunStatus.paused)
      ) {
        handleRef.current = connectRunWs({
          runId,
          accessToken: token,
          onEvent: (ev) => handleForgeWsEvent(ev, eventBridge(gameId, runId)),
          onError: () => setErr(t('generationFailed')),
        })
      }
    } catch (e) {
      setErr(formatApiError(e, t('generationFailed')))
    } finally {
      setRetryBusy(false)
    }
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

  async function onApproveHitl(
    doc: HitlWaitPayload['design_doc'],
    modifyText?: string | null,
  ) {
    if (trial || !runId || !gameId || !token || !hitl) return
    setBusy(true)
    const parsedGameplay =
      typeof doc === 'object' && doc && 'gameplay' in doc ? String(doc.gameplay) : String(doc)
    const parsedControls =
      typeof doc === 'object' && doc && 'controls' in doc ? String(doc.controls) : ''
    const origGameplay =
      typeof hitl.design_doc === 'object' && hitl.design_doc && 'gameplay' in hitl.design_doc
        ? String(hitl.design_doc.gameplay)
        : String(hitl.design_doc)
    const origControls =
      typeof hitl.design_doc === 'object' && hitl.design_doc && 'controls' in hitl.design_doc
        ? String(hitl.design_doc.controls)
        : ''
    const modified =
      parsedGameplay !== origGameplay ||
      parsedControls !== origControls ||
      Boolean(modifyText?.trim())
    try {
      await gamesApi.resolveHitl(
        gameId,
        runId,
        {
          node: hitl.node,
          decision: modified ? 'modify' : 'approve',
          modify_text: modified
            ? modifyText?.trim() ||
              `gameplay: ${parsedGameplay}\ncontrols: ${parsedControls}`
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
          content: `${t('designApproved')} (${t('gameplay')}: ${parsedGameplay.slice(0, 48)}…)`,
        },
      ])
      pushItem({ label: t('hitlApproved'), detail: parsedGameplay.slice(0, 32), tone: 'ok' })
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
          onEvent: (ev) => handleForgeWsEvent(ev, eventBridge(gameId, runId)),
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

  async function submitPublish(note: string, version?: number) {
    if (trial) {
      setErr(t('trialGamesHint'))
      return
    }
    if (!gameId || !token || !detail.data) return
    const publishVersion = version ?? detail.data.current_version
    if (publishVersion < 1) {
      setErr(t('generationFailed'))
      return
    }
    setPublishing(true)
    setErr(null)
    try {
      await gamesApi.submitPublish(gameId, publishVersion, note || t('publishFromForge'), token)
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

  function onPreviewVersion(version: number) {
    if (!gameId) return
    setPreviewVersion(version)
  setPreviewUrl(draftArtifactUrl(gameId, version))
  setSideTab('play')
  setRightTab('preview')
  setStageOpen(true)
}

  async function reconnectToRun(run: RunListItem) {
    if (!token || !gameId || trial) return
    setReconnectingRunId(run.run_id)
    setErr(null)
    closeHandle()
    try {
      const detail = await gamesApi.getRun(run.run_id, token)
      setRunId(detail.run_id)
      setRunStatus(detail.status as RunStatus)
      const hitlPayload = buildResumeHitl(detail, title)
      if (hitlPayload) {
        setHitl(hitlPayload)
        setPhase('paused')
        setBusy(false)
      } else if (detail.status === 'failed') {
        setPhase('idle')
        setBusy(false)
        setHitl(null)
        setRunErrors((prev) => ({
          ...prev,
          [run.run_id]: prev[run.run_id] ?? t('runFailedError'),
        }))
      } else {
        setHitl(null)
        setPhase(detail.phase)
        setBusy(detail.status === 'running')
      }
      if (detail.status === 'running' || detail.status === 'paused') {
        handleRef.current = connectRunWs({
          runId: detail.run_id,
          accessToken: token,
          onEvent: (ev) => handleForgeWsEvent(ev, eventBridge(gameId, detail.run_id)),
          onError: () => setErr(t('generationFailed')),
        })
      }
      setRightTab('preview')
      setStageOpen(true)
    } catch (e) {
      setErr(formatApiError(e, t('resumeFailed')))
    } finally {
      setReconnectingRunId(null)
    }
  }

  const stageStatus = previewUrl ? t('forgeStageStatusReady') : busy ? t('buildingPlayable') : t('ready')

  return (
    <div className="gf-forge-hero">
      <div className="gf-forge-grid-bg" aria-hidden />

      <header className="gf-forge-toolbar flex shrink-0 flex-wrap items-center justify-between gap-3">
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
          <span className="gf-font-display truncate font-medium text-[var(--gf-text)]">{title}</span>
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
          {currentModel ? (
            <span className="hidden font-mono text-[10px] gf-page-muted lg:inline">
              {t('currentModel')}: {currentModel}
            </span>
          ) : null}
          {token && !trial ? (
            <LlmConfigSelect
              accessToken={token}
              value={llmConfigId}
              onChange={setLlmConfigId}
              disabled={busy}
              className="hidden md:flex"
            />
          ) : null}
          {busy || previewUrl || runId || stageOpen ? (
            <Button
              variant="ghost"
              className="!h-9 !rounded-lg !px-2.5 text-xs !text-[var(--gf-text)]"
              onClick={() => setStageOpen((open) => !open)}
            >
              {stageOpen ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRightOpen className="h-3.5 w-3.5" />}
              {stageOpen ? t('forgeHidePreview') : t('forgeShowPreview')}
            </Button>
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
        <p
          role="alert"
          className="relative z-[1] mx-3 mt-2 shrink-0 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 md:mx-4"
        >
          {err}
        </p>
      ) : null}

      <ForgeSplitLayout
        stageOpen={stageOpen}
        left={
          <>
            <ForgeAiStatusBar busy={busy && !hitl} />
            <div className="gf-forge-workspace-scroll">
              <ChatPanel
                variant="forge-hero"
                scrollMode="document"
                messages={messages}
                input={input}
                onInputChange={setInput}
                onSend={onSend}
                disabled={busy || trial}
                streaming={busy && !hitl}
                showComposer={!trial}
                placeholder={previewUrl ? t('describeIteration') : t('describeNewGame')}
              />

              {(items.length > 0 || hitl || busy || phase !== 'idle' || showFailureRecovery) ? (
                <div className="gf-forge-panel-meta space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-mono text-[10px] tracking-[0.14em] text-[var(--gf-text-muted)] uppercase">
                      {t('generationFlow')}
                    </p>
                    {currentModel ? (
                      <p className="font-mono text-[10px] text-[var(--gf-text-muted)]">
                        {t('currentModel')}: {currentModel}
                      </p>
                    ) : null}
                  </div>
                  {(busy || phase !== 'idle' || items.length > 0) ? (
                    <StagePipeline runPhase={phase} stages={stagePipeline} />
                  ) : null}
                  <RunTimeline
                    phase={phase}
                    items={items}
                    className="!rounded-xl border !border-[var(--gf-border)] !bg-white/70"
                  />
                  {showFailureRecovery && runId ? (
                    <FailureRecoveryBar
                      runId={runId}
                      errorSummary={failureSummary}
                      onRevise={onReviseRequirement}
                      onRetry={() => void retryFailedRun()}
                      busy={retryBusy || busy}
                    />
                  ) : null}
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
                !gameId ? (
                  <div className="gf-forge-panel-footer">
                    <TemplatePicker
                      selectedId={selectedTemplateId}
                      onSelect={(tpl: GameTemplate) => {
                        setSelectedTemplateId(tpl.template_id)
                        if (tpl.requirement_seed) setInput(tpl.requirement_seed)
                      }}
                    />
                  </div>
                ) : (
                  <div className="gf-forge-panel-footer">
                    <ForgeQuickTemplates onPick={setInput} />
                  </div>
                )
              ) : (
                <p className="gf-banner-warn gf-forge-panel-footer text-xs">{t('trialForgeLocked')}</p>
              )}
            </div>
          </>
        }
        right={
          <>
            <div className="gf-forge-stage-chrome">
              <div className="flex flex-wrap items-center gap-3">
                <div className="gf-forge-traffic" aria-hidden>
                  <span className="bg-rose-400" />
                  <span className="bg-amber-400" />
                  <span className="bg-emerald-400" />
                </div>
                <span className="font-mono text-[10px] tracking-[0.12em] text-[var(--gf-text-muted)] uppercase">
                  {t('previewStage')}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                {(
                  [
                    ['preview', t('forgeTabPreview')],
                    ...(gameId && detail.data && detail.data.current_version >= 1
                      ? ([['versions', t('forgeTabVersions')]] as const)
                      : []),
                    ...(gameId ? ([['runs', t('forgeTabRuns')]] as const) : []),
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setRightTab(id)}
                    className={cn(
                      'cursor-pointer rounded-lg px-2.5 py-1 font-mono text-[10px] tracking-wide uppercase transition',
                      rightTab === id
                        ? 'gf-bg-accent-soft gf-text-accent'
                        : 'text-[var(--gf-text-muted)] hover:bg-black/[0.04]',
                    )}
                  >
                    {label}
                  </button>
                ))}
                {rightTab === 'preview' && previewUrl ? (
                  <button
                    type="button"
                    title={t('fullscreenPlay')}
                    aria-label={t('fullscreenPlay')}
                    onClick={enterFullscreen}
                    className="ml-1 grid h-8 w-8 cursor-pointer place-items-center rounded-lg text-[var(--gf-text-muted)] transition hover:bg-black/[0.04] hover:text-[var(--gf-text)]"
                  >
                    <Maximize2 className="h-3.5 w-3.5" />
                  </button>
                ) : null}
                <button
                  type="button"
                  title={t('forgeHidePreview')}
                  aria-label={t('forgeHidePreview')}
                  onClick={() => setStageOpen(false)}
                  className="ml-1 grid h-8 w-8 cursor-pointer place-items-center rounded-lg text-[var(--gf-text-muted)] transition hover:bg-black/[0.04] hover:text-[var(--gf-text)]"
                >
                  <PanelRightClose className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div
              ref={stageRef}
              className={cn(
                'gf-forge-stage-canvas',
                flashRing && rightTab === 'preview' && previewUrl ? 'gf-forge-flash-ring' : null,
              )}
            >
              {rightTab === 'preview' ? (
                previewUrl ? (
                  <GamePlayer src={previewUrl} title={title} variant="stage" accessToken={token} />
                ) : (
                  <div className="grid h-full min-h-[220px] place-items-center px-6 text-center">
                    <div className="max-w-sm">
                      <div className="gf-forge-stage-empty-icon mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-[var(--gf-border)] bg-white/80">
                        <Box className="gf-text-accent h-6 w-6" />
                      </div>
                      <p className="mt-4 text-sm leading-relaxed text-[var(--gf-text-muted)]">
                        {busy ? t('buildingPlayable') : t('forgeStageEmpty')}
                      </p>
                    </div>
                  </div>
                )
              ) : rightTab === 'versions' && gameId && detail.data ? (
                <VersionTimeline
                  gameId={gameId}
                  currentVersion={detail.data.current_version}
                  latestVersion={latestVersion}
                  embeddedVersions={detail.data.versions}
                  accessToken={token!}
                  readOnly={trial}
                  previewVersion={previewVersion}
                  onPreview={onPreviewVersion}
                  onActivated={() => void detail.refetch()}
                />
              ) : rightTab === 'runs' && gameId && token ? (
                <RunHistoryPanel
                  gameId={gameId}
                  accessToken={token}
                  currentRunId={runId}
                  onReconnect={(run) => void reconnectToRun(run)}
                  reconnectingId={reconnectingRunId}
                  runErrors={runErrors}
                />
              ) : null}
            </div>

            <footer className="gf-forge-stage-footer">
              <span>{stageStatus}</span>
              <span className="flex items-center gap-1.5">
                <span
                  className={cn(
                    'inline-block h-1.5 w-1.5 rounded-full',
                    busy ? 'animate-pulse bg-amber-400' : previewUrl ? 'bg-emerald-500' : 'bg-[var(--gf-text-muted)]',
                  )}
                  aria-hidden
                />
                {previewUrl ? t('playable') : busy ? t('building') : t('ready')}
              </span>
            </footer>
          </>
        }
      />

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
