import { useEffect, useMemo, useRef, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
} from "lucide-react";
import { gamesApi } from "@/api/games";
import { RunPhase, RunStatus } from "@/api/enums";
import { formatApiError } from "@/api/error-message";
import type { HitlWaitPayload } from "@/api/ws-types";
import { ChatPanel, type ChatMsg } from "@/components/forge/ChatPanel";
import { ForgeAiStatusBar } from "@/components/forge/ForgeAiStatusBar";
import { ForgeLogDock } from "@/components/forge/ForgeLogDock";
import { ForgeQuickTemplates } from "@/components/forge/ForgeQuickTemplates";
import { ForgeSplitLayout } from "@/components/forge/ForgeSplitLayout";
import { HitlCard } from "@/components/forge/HitlCard";
import { LlmConfigSelect } from "@/components/forge/LlmConfigSelect";
import { RunHistoryPanel } from "@/components/forge/RunHistoryPanel";
import type { TimelineItem } from "@/components/forge/RunTimeline";
import { TemplatePicker } from "@/components/forge/TemplatePicker";
import { VersionTimeline } from "@/components/forge/VersionTimeline";
import { GamePlayer } from "@/components/game/GamePlayer";
import { PublishNoteModal } from "@/components/games/PublishNoteModal";
import { Button } from "@/components/ui/button";
import { isFailureHitlNode } from "@/lib/hitl-design-doc";
import { isTrialUser } from "@/lib/trial";
import {
  applyPhaseStart,
  emptyStagePipeline,
  type StagePipelineState,
} from "@/lib/stage-pipeline-state";
import { useT } from "@/i18n/use-t";
import { useAuthStore } from "@/stores/auth-store";
import { useLocaleStore } from "@/stores/locale-store";
import { connectRunWs, type RunWsHandle } from "@/ws/client";
import { handleForgeWsEvent } from "./forge-events";
import {
  buildResumeHitl,
  pickActiveRun,
  previewFromGameDetail,
  syncUiFromRun,
} from "./resume";
import { draftArtifactUrl } from "@/lib/hosting";
import {
  clearActiveRun,
  readActiveRun,
  saveActiveRun,
} from "@/lib/active-run-storage";
import { getTemplateById } from "@/constants/templates";
import { templatesApi, type GameTemplate } from "@/api/templates";
import type { RunListItem } from "@/api/types";
import { cn } from "@/lib/cn";

function mid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ForgePage() {
  const t = useT();
  const { gameId: routeGameId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const token = useAuthStore((s) => s.access_token);
  const user = useAuthStore((s) => s.user);
  const trial = isTrialUser(user);
  const locale = useLocaleStore((s) => s.locale);

  const [gameId, setGameId] = useState(routeGameId);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>(() => [
    {
      id: "m0",
      role: "assistant",
      content: t("forgeWelcome"),
    },
  ]);
  const [phase, setPhase] = useState<RunPhase | "idle" | "paused">("idle");
  const [items, setItems] = useState<TimelineItem[]>([]);
  const [hitl, setHitl] = useState<HitlWaitPayload | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [, setSideTab] = useState<"log" | "play">("log");
  const [runId, setRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus | "idle">("idle");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [previewVersion, setPreviewVersion] = useState<number | null>(null);
  const [quotaHint, setQuotaHint] = useState<string | null>(null);
  const [llmConfigId, setLlmConfigId] = useState<string | null>(null);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [rightTab, setRightTab] = useState<"preview" | "versions" | "runs">(
    "preview",
  );
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    null,
  );
  const [runErrors, setRunErrors] = useState<Record<string, string>>({});
  const [reconnectingRunId, setReconnectingRunId] = useState<string | null>(
    null,
  );
  const [flashRing, setFlashRing] = useState(false);
  const [stageOpen, setStageOpen] = useState(true);
  const [logDockOpen, setLogDockOpen] = useState(false);
  const [stagePipeline, setStagePipeline] =
    useState<StagePipelineState>(emptyStagePipeline);
  const [retryBusy, setRetryBusy] = useState(false);
  const handleRef = useRef<RunWsHandle | null>(null);
  const resumedRef = useRef<string | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const prevPreviewRef = useRef<string | null>(null);

  const detail = useQuery({
    queryKey: ["game", gameId],
    enabled: Boolean(gameId && token),
    queryFn: () => gamesApi.get(gameId!, token!),
  });

  const title = useMemo(() => {
    if (detail.data?.title) return detail.data.title;
    if (gameId) return `${t("editGame")} ${gameId}`;
    return t("newGame");
  }, [detail.data?.title, gameId, locale]);

  const latestVersion = useMemo(() => {
    const vers = detail.data?.versions ?? [];
    if (vers.length === 0) return detail.data?.current_version ?? 0;
    return Math.max(...vers.map((v) => v.version));
  }, [detail.data?.versions, detail.data?.current_version]);

  const showFailureRecovery = Boolean(
    !trial &&
    runId &&
    (runStatus === RunStatus.failed ||
      (hitl != null && isFailureHitlNode(hitl.node))),
  );
  const failureSummary = runId ? runErrors[runId] : undefined;

  useEffect(() => {
    if (showFailureRecovery) setLogDockOpen(true);
  }, [showFailureRecovery]);

  useEffect(() => {
    const tplId = searchParams.get("template");
    if (!tplId || gameId) return;
    void templatesApi.list().then((list) => {
      const tpl = list.find((t) => t.template_id === tplId) ?? null;
      if (tpl) {
        setSelectedTemplateId(tpl.template_id);
        if (tpl.requirement_seed) setInput(tpl.requirement_seed);
        return;
      }
      const legacy = getTemplateById(tplId);
      if (legacy) {
        setSelectedTemplateId(legacy.id);
        if (legacy.requirement_seed) setInput(legacy.requirement_seed);
      }
    });
  }, [searchParams, gameId]);

  useEffect(() => {
    setGameId(routeGameId);
    resumedRef.current = null;
  }, [routeGameId]);

  useEffect(() => {
    setMessages((current) =>
      current.map((message) =>
        message.id === "m0"
          ? { ...message, content: t("forgeWelcome") }
          : message,
      ),
    );
  }, [locale]);
  useEffect(
    () => () => {
      const h = handleRef.current;
      h?.close();
    },
    [],
  );

  useEffect(() => {
    if (!previewUrl || previewUrl === prevPreviewRef.current) return;
    prevPreviewRef.current = previewUrl;
    setFlashRing(true);
    const timer = window.setTimeout(() => setFlashRing(false), 900);
    return () => window.clearTimeout(timer);
  }, [previewUrl]);

  function connectWs(activeGameId: string, activeRunId: string) {
    if (!token) return;
    const prev = handleRef.current;
    prev?.close();
    handleRef.current = connectRunWs({
      runId: activeRunId,
      accessToken: token!,
      persistent: true,
      onEvent: (ev) =>
        handleForgeWsEvent(ev, eventBridge(activeGameId, activeRunId)),
      onError: () => setErr(t("generationFailed")),
    });
  }

  // 进入已有游戏：恢复未结束 run + 重连 WS；有版本则挂草稿预览
  useEffect(() => {
    if (!gameId || !token) return;
    if (resumedRef.current === gameId) return;
    let cancelled = false;

    async function resume() {
      try {
        const game = detail.data ?? (await gamesApi.get(gameId!, token!));
        if (cancelled) return;
        const preview = previewFromGameDetail(game);
        if (preview && !previewUrl) {
          setPreviewUrl(preview);
          setPreviewVersion(game.current_version);
          setSideTab("play");
        }

        if (isTrialUser(user)) {
          resumedRef.current = gameId!;
          return;
        }

        const listed = await gamesApi.listRuns(gameId!, token!);
        if (cancelled) return;
        let active = pickActiveRun(listed.data);

        if (!active) {
          const saved = readActiveRun();
          if (saved && saved.gameId === gameId) {
            const savedRun = await gamesApi.getRun(saved.runId, token!);
            if (savedRun.status === "done" || savedRun.status === "failed") {
              clearActiveRun(saved.runId);
              if (savedRun.status === "done") {
                await detail.refetch();
                const refreshed = previewFromGameDetail(
                  (await gamesApi.get(gameId!, token!)) as typeof game,
                );
                if (refreshed) setPreviewUrl(refreshed);
              }
            } else {
              active = {
                run_id: savedRun.run_id,
                status: savedRun.status,
                phase: savedRun.phase,
                started_at: "",
                ended_at: null,
              };
            }
          }
        }

        if (!active) {
          resumedRef.current = gameId!;
          return;
        }

        const run = await gamesApi.getRun(active.run_id, token!);
        if (cancelled) return;
        setRunId(run.run_id);
        const ui = syncUiFromRun(run, game.title);
        setRunStatus(ui.runStatus);
        setHitl(ui.hitl);
        setPhase(ui.phase);
        setBusy(ui.busy);
        if (ui.busy || ui.hitl) setStageOpen(true);
        saveActiveRun(gameId!, run.run_id);
        pushItem({ label: t("runResumed"), detail: run.run_id, tone: "info" });
        connectWs(gameId!, run.run_id);
        resumedRef.current = gameId!;
      } catch {
        resumedRef.current = gameId!;
      }
    }

    void resume();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅在 gameId/token/detail 就绪时恢复一次
  }, [gameId, token, detail.data?.game_id]);

  // WS 断线时的 HTTP 轮询兜底
  useEffect(() => {
    if (!runId || !token || !gameId) return;
    if (runStatus !== RunStatus.running && runStatus !== RunStatus.paused)
      return;
    const timer = window.setInterval(async () => {
      try {
        const run = await gamesApi.getRun(runId, token);
        if (run.status === "done" || run.status === "failed") {
          clearActiveRun(runId);
          setRunStatus(run.status);
          setBusy(false);
          if (run.status === "done") {
            setPhase(RunPhase.done);
            void detail.refetch();
          } else {
            setPhase("idle");
          }
        }
      } catch {
        /* ignore transient poll errors */
      }
    }, 8000);
    return () => window.clearInterval(timer);
  }, [runId, token, gameId, runStatus, detail]);

  function pushItem(
    partial: Omit<TimelineItem, "id" | "at"> & { at?: string },
  ) {
    setItems((prev) =>
      [
        {
          id: mid("ev"),
          at: partial.at ?? new Date().toISOString(),
          ...partial,
        },
        ...prev,
      ].slice(0, 80),
    );
  }

  function eventBridge(
    activeGameId = gameId,
    activeRunId: string | null = runId,
  ) {
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
        setRunErrors((prev) => ({ ...prev, [rid]: message }));
        setRunStatus(RunStatus.failed);
        clearActiveRun(rid);
      },
      onRunFinished: () => {
        if (activeRunId) clearActiveRun(activeRunId);
      },
      setStagePipeline,
      gameId: activeGameId,
      runId: activeRunId,
      t,
    };
  }

  function closeHandle() {
    handleRef.current?.close();
    handleRef.current = null;
  }

  async function startGeneration(requirement: string) {
    if (!token || !user) return;
    setErr(null);
    setBusy(true);
    setHitl(null);
    setPreviewUrl(null);
    setSideTab("log");
    setStagePipeline(applyPhaseStart(emptyStagePipeline(), RunPhase.plan));
    closeHandle();

    try {
      let gid = gameId;
      if (!gid) {
        const created = await gamesApi.create(
          requirement.slice(0, 24) || t("newGame"),
          requirement,
          token,
        );
        gid = created.game_id;
        setGameId(gid);
        navigate(`/forge/${gid}`, { replace: true });
      }
      const run = await gamesApi.startRun(gid, requirement, token, llmConfigId);
      setRunId(run.run_id);
      setRunStatus(RunStatus.running);
      setPhase(RunPhase.plan);
      saveActiveRun(gid, run.run_id);
      pushItem({ label: t("runStarting"), detail: run.run_id, tone: "info" });
      const onEvent = (ev: Parameters<typeof handleForgeWsEvent>[0]) =>
        handleForgeWsEvent(ev, eventBridge(gid, run.run_id));
      handleRef.current = connectRunWs({
        runId: run.run_id,
        accessToken: token,
        persistent: true,
        onEvent,
        onError: () => setErr(t("generationFailed")),
      });
    } catch (e) {
      setBusy(false);
      setPhase("idle");
      const msg = formatApiError(e, t("generationFailed"));
      setErr(msg);
      setMessages((m) => [
        ...m,
        {
          id: mid("m"),
          role: "assistant",
          content: `${t("generationFailed")}: ${msg}`,
        },
      ]);
    }
  }

  function onSend() {
    const text = input.trim();
    if (!text || busy) return;
    if (trial) {
      setErr(t("trialForgeLocked"));
      return;
    }
    setMessages((m) => [...m, { id: mid("m"), role: "user", content: text }]);
    setInput("");
    setStageOpen(true);
    void startGeneration(text);
  }

  function onReviseRequirement() {
    setInput(t("failureReviseTemplate"));
  }

  async function retryFailedRun() {
    if (!runId || !token || trial) return;
    setRetryBusy(true);
    setErr(null);
    try {
      const resp = await gamesApi.retryRun(runId, token);
      setRunStatus(resp.status as RunStatus);
      setPhase(resp.phase);
      setBusy(resp.status === RunStatus.running);
      setHitl(null);
      setRunErrors((prev) => {
        const next = { ...prev };
        delete next[runId];
        return next;
      });
      pushItem({ label: t("failureRetry"), detail: runId, tone: "info" });
      if (
        !handleRef.current &&
        gameId &&
        (resp.status === RunStatus.running || resp.status === RunStatus.paused)
      ) {
        connectWs(gameId, runId);
      }
    } catch (e) {
      setErr(formatApiError(e, t("generationFailed")));
    } finally {
      setRetryBusy(false);
    }
  }

  function reportBug() {
    if (trial) {
      setErr(t("trialForgeLocked"));
      return;
    }
    setInput(t("bugPrompt"));
  }

  function enterFullscreen() {
    if (!stageRef.current?.requestFullscreen) return;
    void stageRef.current.requestFullscreen();
  }

  async function onApproveHitl(
    doc: HitlWaitPayload["design_doc"],
    modifyText?: string | null,
  ) {
    if (trial || !runId || !gameId || !token || !hitl) return;
    setBusy(true);
    const parsedGameplay =
      typeof doc === "object" && doc && "gameplay" in doc
        ? String(doc.gameplay)
        : String(doc);
    const parsedControls =
      typeof doc === "object" && doc && "controls" in doc
        ? String(doc.controls)
        : "";
    const origGameplay =
      typeof hitl.design_doc === "object" &&
      hitl.design_doc &&
      "gameplay" in hitl.design_doc
        ? String(hitl.design_doc.gameplay)
        : String(hitl.design_doc);
    const origControls =
      typeof hitl.design_doc === "object" &&
      hitl.design_doc &&
      "controls" in hitl.design_doc
        ? String(hitl.design_doc.controls)
        : "";
    const modified =
      parsedGameplay !== origGameplay ||
      parsedControls !== origControls ||
      Boolean(modifyText?.trim());
    try {
      await gamesApi.resolveHitl(
        gameId,
        runId,
        {
          node: hitl.node,
          decision: modified ? "modify" : "approve",
          modify_text: modified
            ? modifyText?.trim() ||
              `gameplay: ${parsedGameplay}\ncontrols: ${parsedControls}`
            : null,
        },
        token,
      );
      setHitl(null);
      setPhase(RunPhase.art);
      setRunStatus(RunStatus.running);
      setMessages((m) => [
        ...m,
        {
          id: mid("m"),
          role: "assistant",
          content: `${t("designApproved")} (${t("gameplay")}: ${parsedGameplay.slice(0, 48)}…)`,
        },
      ]);
      pushItem({
        label: t("hitlApproved"),
        detail: parsedGameplay.slice(0, 32),
        tone: "ok",
      });
      // real：继续复用已连接的 WS，后端 resume 后推事件
    } catch (e) {
      setBusy(false);
      setErr(formatApiError(e, t("generationFailed")));
    }
  }

  function onRejectHitl() {
    // 契约仅有 approve|modify（都会 resume）；拒绝 = 本地中止并断开 WS，不调 resolve
    setHitl(null);
    setBusy(false);
    setRunStatus("idle");
    setPhase("idle");
    closeHandle();
    pushItem({ label: t("hitlRejected"), tone: "err" });
    setMessages((m) => [
      ...m,
      { id: mid("m"), role: "assistant", content: t("runStopped") },
    ]);
  }

  async function pauseRun() {
    if (!runId || !token || trial) return;
    try {
      const resp = await gamesApi.pauseRun(runId, token);
      setRunStatus(resp.status as RunStatus);
      setPhase("paused");
      setBusy(false);
      pushItem({ label: t("runPaused"), detail: runId, tone: "info" });
    } catch (e) {
      setErr(formatApiError(e, t("pauseFailed")));
    }
  }

  async function resumeRun() {
    if (!runId || !token || trial || hitl) return;
    try {
      const resp = await gamesApi.resumeRun(runId, token);
      setRunStatus(resp.status as RunStatus);
      setPhase(resp.phase);
      setBusy(true);
      pushItem({ label: t("runResumed"), detail: runId, tone: "info" });
      if (!handleRef.current && gameId) {
        connectWs(gameId, runId);
      }
    } catch (e) {
      setErr(formatApiError(e, t("resumeFailed")));
    }
  }

  async function cancelRun() {
    if (!runId || !token || trial) return;
    try {
      const resp = await gamesApi.cancelRun(runId, token);
      setRunStatus(resp.status as RunStatus);
      setBusy(false);
      setPhase("idle");
      setHitl(null);
      closeHandle();
      clearActiveRun(runId); // 清本地 active-run，避免刷新后被 resume 兜底重新拉起已取消的 run
      void qc.invalidateQueries({ queryKey: ["active-runs"] }); // 立即刷新全局 ActiveRunBanner
      pushItem({ label: t("runCancelled"), detail: runId, tone: "err" });
    } catch (e) {
      setErr(formatApiError(e, t("cancelFailed")));
      // 取消失败：同步后端真实状态，避免 UI 误显示为「已取消」而 run 实际仍在跑
      try {
        const run = await gamesApi.getRun(runId, token);
        setRunStatus(run.status as RunStatus);
      } catch {
        /* 忽略二次失败：保留上方的取消失败提示即可 */
      }
    }
  }

  const canPause = Boolean(
    runId && runStatus === RunStatus.running && !hitl && !trial,
  );
  const canResume = Boolean(
    runId && runStatus === RunStatus.paused && !hitl && !trial,
  );
  const canCancel = Boolean(
    runId &&
    (runStatus === RunStatus.running || runStatus === RunStatus.paused) &&
    !trial,
  );

  async function submitPublish(note: string, version?: number) {
    if (trial) {
      setErr(t("trialGamesHint"));
      return;
    }
    if (!gameId || !token || !detail.data) return;
    const publishVersion = version ?? detail.data.current_version;
    if (publishVersion < 1) {
      setErr(t("generationFailed"));
      return;
    }
    setPublishing(true);
    setErr(null);
    try {
      await gamesApi.submitPublish(
        gameId,
        publishVersion,
        note || t("publishFromForge"),
        token,
      );
      await detail.refetch();
      setPublishOpen(false);
      pushItem({ label: t("publishSubmittedMsg"), tone: "ok" });
    } catch (e) {
      setErr(formatApiError(e, t("submitPublishFailed")));
    } finally {
      setPublishing(false);
    }
  }

  function onPreviewVersion(version: number) {
    if (!gameId) return;
    setPreviewVersion(version);
    setPreviewUrl(draftArtifactUrl(gameId, version));
    setSideTab("play");
    setRightTab("preview");
    setStageOpen(true);
  }

  async function reconnectToRun(run: RunListItem) {
    if (!token || !gameId || trial) return;
    setReconnectingRunId(run.run_id);
    setErr(null);
    closeHandle();
    try {
      const detail = await gamesApi.getRun(run.run_id, token);
      setRunId(detail.run_id);
      setRunStatus(detail.status as RunStatus);
      const hitlPayload = buildResumeHitl(detail, title);
      if (hitlPayload) {
        setHitl(hitlPayload);
        setPhase("paused");
        setBusy(false);
      } else if (detail.status === "failed") {
        setPhase("idle");
        setBusy(false);
        setHitl(null);
        setRunErrors((prev) => ({
          ...prev,
          [run.run_id]: prev[run.run_id] ?? t("runFailedError"),
        }));
      } else {
        setHitl(null);
        setPhase(detail.phase);
        setBusy(detail.status === "running");
      }
      if (detail.status === "running" || detail.status === "paused") {
        connectWs(gameId, detail.run_id);
      }
      setRightTab("preview");
      setStageOpen(true);
    } catch (e) {
      setErr(formatApiError(e, t("resumeFailed")));
    } finally {
      setReconnectingRunId(null);
    }
  }

  const stageStatus = previewUrl
    ? t("forgeStageStatusReady")
    : busy
      ? t("buildingPlayable")
      : t("ready");

  return (
    <div
      className={cn(
        "gf-forge-hero isolate flex min-h-0 flex-col overflow-hidden bg-[#f3f5f7]",
        stageOpen && "gf-forge-hero--stage-open",
      )}
    >
      <div className="gf-forge-grid-bg" aria-hidden />

      <header className="gf-forge-toolbar relative z-[2] flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-black/[0.07] bg-white/90 px-3 py-3 backdrop-blur-xl md:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            to="/games"
            title={t("backToGames")}
            aria-label={t("backToGames")}
            className="gf-interactive gf-border-subtle grid h-10 w-10 shrink-0 place-items-center rounded-xl border bg-white gf-page-muted transition-[border-color,color,background-color] hover:border-[rgba(var(--gf-primary-rgb),0.3)] hover:bg-[rgba(var(--gf-primary-rgb),0.05)] hover:text-[var(--gf-primary)] focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.3)]"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] gf-page-muted">
                {t("forge")}
              </span>
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ring-1",
                  busy
                    ? "bg-amber-50 text-amber-700 ring-amber-200"
                    : previewUrl
                      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                      : "gf-bg-accent-soft gf-text-accent ring-[rgba(var(--gf-primary-rgb),0.15)]",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    busy
                      ? "animate-pulse bg-amber-500 motion-reduce:animate-none"
                      : previewUrl
                        ? "bg-emerald-500"
                        : "bg-[var(--gf-primary)]",
                  )}
                  aria-hidden="true"
                />
                {previewUrl ? t("playable") : busy ? t("building") : t("ready")}
              </span>
            </div>
            <h1 className="gf-font-display mt-0.5 truncate text-base font-semibold tracking-[-0.01em] text-[var(--gf-text)] md:text-lg">
              {title}
            </h1>
          </div>
        </div>

        <div className="flex min-w-0 shrink-0 flex-wrap items-center justify-end gap-1.5">
          {quotaHint ? (
            <span className="hidden max-w-40 truncate font-mono text-[10px] gf-page-muted xl:inline">
              {quotaHint}
            </span>
          ) : null}
          {currentModel ? (
            <span className="hidden max-w-48 truncate font-mono text-[10px] gf-page-muted 2xl:inline">
              {t("currentModel")}: {currentModel}
            </span>
          ) : null}
          {token && !trial ? (
            <LlmConfigSelect
              accessToken={token}
              value={llmConfigId}
              onChange={setLlmConfigId}
              disabled={busy}
              className="hidden w-56 lg:flex"
            />
          ) : null}
          {canPause ? (
            <Button
              variant="ghost"
              className="!min-h-10 !rounded-xl !px-3 text-xs !text-[var(--gf-text)]"
              onClick={() => void pauseRun()}
            >
              <Pause className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden xl:inline">{t("pauseRun")}</span>
            </Button>
          ) : null}
          {canResume ? (
            <Button
              variant="ghost"
              className="gf-text-accent !min-h-10 !rounded-xl !px-3 text-xs"
              onClick={() => void resumeRun()}
            >
              <Play className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden xl:inline">{t("resumeRunBtn")}</span>
            </Button>
          ) : null}
          {canCancel ? (
            <Button
              variant="ghost"
              className="!min-h-10 !rounded-xl !px-3 text-xs !text-rose-600"
              onClick={() => void cancelRun()}
            >
              <Square className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden xl:inline">{t("cancelRunBtn")}</span>
            </Button>
          ) : null}
          {busy || previewUrl || runId || stageOpen ? (
            <Button
              variant="ghost"
              className="!min-h-10 !rounded-xl !px-3 text-xs !text-[var(--gf-text)]"
              onClick={() => setStageOpen((open) => !open)}
            >
              {stageOpen ? (
                <PanelRightClose className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <PanelRightOpen className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              <span className="hidden sm:inline">
                {stageOpen ? t("forgeHidePreview") : t("forgeShowPreview")}
              </span>
            </Button>
          ) : null}
          <button
            type="button"
            title={t("captureIssue")}
            aria-label={t("captureIssue")}
            onClick={reportBug}
            disabled={trial}
            className="gf-interactive gf-border-subtle grid h-10 w-10 cursor-pointer place-items-center rounded-xl border bg-black/[0.025] gf-page-muted transition-[border-color,color,background-color] hover:border-[rgba(var(--gf-primary-rgb),0.3)] hover:bg-[rgba(var(--gf-primary-rgb),0.05)] hover:text-[var(--gf-primary)] focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.3)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Bug className="h-4 w-4" aria-hidden="true" />
          </button>
          {gameId &&
          !trial &&
          detail.data &&
          detail.data.current_version >= 1 ? (
            <Button
              variant="primary"
              className="gf-btn-primary !min-h-10 !rounded-xl !border-0 !px-3 text-xs"
              disabled={publishing || busy}
              onClick={() => setPublishOpen(true)}
            >
              {publishing ? (
                <Loader2
                  className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none"
                  aria-hidden="true"
                />
              ) : (
                <Upload className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              <span className="hidden sm:inline">{t("submitPublishBtn")}</span>
            </Button>
          ) : null}
        </div>
      </header>

      {err ? (
        <p
          role="alert"
          className="relative z-[1] mx-3 mt-2 shrink-0 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 shadow-sm md:mx-4"
        >
          {err}
        </p>
      ) : null}

      <ForgeSplitLayout
        stageOpen={stageOpen}
        className="relative z-[1] min-h-0 flex-1 p-3 md:p-4"
        left={
          <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-black/[0.08] bg-[var(--gf-surface)] shadow-[0_12px_32px_rgba(15,23,42,0.06)]">
            <ForgeAiStatusBar busy={busy && !hitl} />
            <ChatPanel
              variant="forge-hero"
              scrollMode="panel"
              className="min-h-0 flex-1"
              messages={messages}
              input={input}
              onInputChange={setInput}
              onSend={onSend}
              disabled={busy || trial}
              streaming={busy && !hitl}
              showComposer={!trial}
              placeholder={
                previewUrl ? t("describeIteration") : t("describeNewGame")
              }
              conversationFooter={
                <>
                  {hitl ? (
                    <HitlCard
                      payload={hitl}
                      onApprove={onApproveHitl}
                      onReject={onRejectHitl}
                      busy={busy || trial}
                    />
                  ) : null}
                  {!trial ? (
                    !gameId ? (
                      <div className="rounded-xl border border-black/[0.06] bg-black/[0.018] p-3">
                        <TemplatePicker
                          selectedId={selectedTemplateId}
                          onSelect={(tpl: GameTemplate) => {
                            setSelectedTemplateId(tpl.template_id);
                            if (tpl.requirement_seed)
                              setInput(tpl.requirement_seed);
                          }}
                        />
                      </div>
                    ) : (
                      <div className="rounded-xl border border-black/[0.06] bg-black/[0.018] p-3">
                        <ForgeQuickTemplates onPick={setInput} />
                      </div>
                    )
                  ) : (
                    <p className="gf-banner-warn rounded-xl p-3 text-xs">
                      {t("trialForgeLocked")}
                    </p>
                  )}
                </>
              }
            />
          </section>
        }
        right={
          <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-black/15 bg-[#101218] shadow-[0_18px_50px_rgba(15,23,42,0.16)]">
            <div className="gf-forge-stage-chrome flex min-h-13 shrink-0 items-center justify-between gap-3 border-b border-white/[0.08] bg-[#151820] px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-3">
                <div className="gf-forge-traffic" aria-hidden>
                  <span className="bg-white/20" />
                  <span className="bg-white/20" />
                  <span
                    className={cn(
                      busy
                        ? "animate-pulse bg-amber-400 motion-reduce:animate-none"
                        : previewUrl
                          ? "bg-emerald-400"
                          : "bg-white/20",
                    )}
                  />
                </div>
                <span className="font-mono text-[10px] tracking-[0.12em] text-white/45 uppercase">
                  {t("previewStage")}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                {(
                  [
                    ["preview", t("forgeTabPreview")],
                    ...(gameId &&
                    detail.data &&
                    detail.data.current_version >= 1
                      ? ([["versions", t("forgeTabVersions")]] as const)
                      : []),
                    ...(gameId ? ([["runs", t("forgeTabRuns")]] as const) : []),
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setRightTab(id)}
                    className={cn(
                      "min-h-8 cursor-pointer rounded-lg px-2.5 py-1 font-mono text-[10px] tracking-wide uppercase transition-[color,background-color] focus-visible:ring-2 focus-visible:ring-white/30",
                      rightTab === id
                        ? "bg-white/10 text-white ring-1 ring-white/10"
                        : "text-white/45 hover:bg-white/[0.06] hover:text-white/80",
                    )}
                  >
                    {label}
                  </button>
                ))}
                {rightTab === "preview" && previewUrl ? (
                  <button
                    type="button"
                    title={t("fullscreenPlay")}
                    aria-label={t("fullscreenPlay")}
                    onClick={enterFullscreen}
                    className="ml-1 grid h-8 w-8 cursor-pointer place-items-center rounded-lg text-white/45 transition-colors hover:bg-white/[0.08] hover:text-white focus-visible:ring-2 focus-visible:ring-white/30"
                  >
                    <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                ) : null}
                <button
                  type="button"
                  title={t("forgeHidePreview")}
                  aria-label={t("forgeHidePreview")}
                  onClick={() => setStageOpen(false)}
                  className="ml-1 grid h-8 w-8 cursor-pointer place-items-center rounded-lg text-white/45 transition-colors hover:bg-white/[0.08] hover:text-white focus-visible:ring-2 focus-visible:ring-white/30"
                >
                  <PanelRightClose className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
            </div>

            <div
              ref={stageRef}
              className={cn(
                "gf-forge-stage-canvas min-h-0 flex-1",
                rightTab === "preview"
                  ? "bg-[#090b10] p-2.5"
                  : "bg-[var(--gf-surface)] p-3",
                flashRing && rightTab === "preview" && previewUrl
                  ? "gf-forge-flash-ring"
                  : null,
              )}
            >
              {rightTab === "preview" ? (
                previewUrl ? (
                  <GamePlayer
                    src={previewUrl}
                    title={title}
                    variant="stage"
                    accessToken={token}
                  />
                ) : (
                  <div className="grid h-full min-h-[320px] place-items-center rounded-xl border border-white/[0.07] bg-[radial-gradient(circle_at_center,rgba(var(--gf-primary-rgb),0.09),transparent_58%)] px-6 text-center">
                    <div className="max-w-sm">
                      <div className="gf-forge-stage-empty-icon mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/[0.05] shadow-[0_0_36px_rgba(var(--gf-primary-rgb),0.12)]">
                        <Box
                          className="h-6 w-6 text-white/70"
                          aria-hidden="true"
                        />
                      </div>
                      <p className="mt-4 text-balance text-sm leading-relaxed text-white/55">
                        {busy ? t("buildingPlayable") : t("forgeStageEmpty")}
                      </p>
                    </div>
                  </div>
                )
              ) : rightTab === "versions" && gameId && detail.data ? (
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
              ) : rightTab === "runs" && gameId && token ? (
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

            <footer className="gf-forge-stage-footer flex min-h-10 shrink-0 items-center justify-between border-t border-white/[0.08] bg-[#151820] px-3 font-mono text-[10px] text-white/45">
              <span>{stageStatus}</span>
              <span className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "inline-block h-1.5 w-1.5 rounded-full",
                    busy
                      ? "animate-pulse bg-amber-400 motion-reduce:animate-none"
                      : previewUrl
                        ? "bg-emerald-400"
                        : "bg-white/25",
                  )}
                  aria-hidden
                />
                {previewUrl ? t("playable") : busy ? t("building") : t("ready")}
              </span>
            </footer>
          </section>
        }
      />

      {items.length > 0 || busy || phase !== "idle" || showFailureRecovery ? (
        <ForgeLogDock
          open={logDockOpen}
          onToggle={() => setLogDockOpen((v) => !v)}
          runPhase={phase}
          stages={stagePipeline}
          items={items}
          currentModel={currentModel}
          failureRecovery={
            showFailureRecovery && runId
              ? {
                  runId,
                  errorSummary: failureSummary,
                  onRevise: onReviseRequirement,
                  onRetry: () => void retryFailedRun(),
                  busy: retryBusy || busy,
                }
              : null
          }
        />
      ) : null}

      <PublishNoteModal
        open={publishOpen}
        gameTitle={title}
        defaultNote=""
        busy={publishing}
        onCancel={() => setPublishOpen(false)}
        onConfirm={(note) => void submitPublish(note)}
      />
    </div>
  );
}
