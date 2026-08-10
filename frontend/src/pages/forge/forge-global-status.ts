import { RunStatus } from "@/api/enums";
import type { MessageKey } from "@/i18n/messages";
import type { HitlWaitPayload } from "@/api/ws-types";

/**
 * 全局运行状态的统一优先级（高 → 低）：
 *   blocked > error > paused > running > completed > ready > idle
 * 所有展示区域（Header / 聊天 / 试玩 / 日志）都应基于此派生状态，
 * 不再各自解读局部字段，避免「就绪」与「无可用 LLM」并存。
 */
export type ForgeStatusLevel =
  | "blocked"
  | "error"
  | "paused"
  | "running"
  | "completed"
  | "ready"
  | "idle";

export type ForgeStatusTone = "rose" | "amber" | "emerald" | "primary" | "slate";

/** Header 徽章 / AiStatusBar 状态点共用：tone → className 映射 */
export const STATUS_BADGE_CLASS: Record<
  ForgeStatusTone,
  { wrap: string; dot: string }
> = {
  rose: {
    wrap: "bg-rose-50 text-rose-700 ring-rose-200",
    dot: "bg-rose-500",
  },
  amber: {
    wrap: "bg-amber-50 text-amber-700 ring-amber-200",
    dot: "animate-pulse bg-amber-500 motion-reduce:animate-none",
  },
  emerald: {
    wrap: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    dot: "bg-emerald-500",
  },
  primary: {
    wrap: "gf-bg-accent-soft gf-text-accent ring-[rgba(var(--gf-primary-rgb),0.15)]",
    dot: "bg-[var(--gf-primary)]",
  },
  slate: {
    wrap: "bg-slate-100 text-slate-600 ring-slate-200",
    dot: "bg-slate-400",
  },
};

export type ForgeGlobalStatus = {
  level: ForgeStatusLevel;
  /** Header 徽章主文案的 i18n key */
  labelKey: MessageKey;
  tone: ForgeStatusTone;
  /** 是否允许发送新需求 */
  canSend: boolean;
  /** 是否处于阻塞态（无 LLM 等）—— 发送按钮应变身、试玩区显示阻塞说明 */
  blocked: boolean;
  /** 阻塞说明 i18n key（仅 blocked 时有意义） */
  blockedReasonKey?: MessageKey;
};

/** 命中即认定失败由 LLM 配置缺失/无效导致（后端文案或错误码） */
const LLM_ERROR_RE = /llm|api[ _]?key|配置无效|no.*configur|invalid.*config/i;

type Input = {
  trial: boolean;
  hasLlmConfig: boolean;
  runStatus: RunStatus | "idle";
  busy: boolean;
  hitl: HitlWaitPayload | null;
  previewUrl: string | null;
  runId: string | null;
  runErrors: Record<string, string>;
};

/**
 * 从 ForgePage 顶层 state 派生唯一的全局状态。纯函数，便于在 useMemo 中调用。
 * 真相源是 { runStatus, phase, hitl, busy, previewUrl, runErrors, hasLlmConfig }。
 */
export function deriveForgeStatus(i: Input): ForgeGlobalStatus {
  const llmMissing = !i.trial && !i.hasLlmConfig;
  const failedMsg = i.runId ? i.runErrors[i.runId] : undefined;
  const failedDueToLlm =
    i.runStatus === RunStatus.failed &&
    Boolean(failedMsg && LLM_ERROR_RE.test(failedMsg));

  // 1. 阻塞：无 LLM 配置，或失败由 LLM 配置导致
  if (llmMissing || failedDueToLlm) {
    return {
      level: "blocked",
      labelKey: "forgeStatusBlockedLlm",
      tone: "rose",
      canSend: false,
      blocked: true,
      blockedReasonKey: "forgeStageBlockedLlm",
    };
  }

  // 2. 错误：run 失败（非 LLM 原因）
  if (i.runStatus === RunStatus.failed) {
    return {
      level: "error",
      labelKey: "forgeStatusFailed",
      tone: "rose",
      canSend: false,
      blocked: false,
    };
  }

  // 3. 暂停：HITL 等待 或 run 暂停
  if (i.hitl || i.runStatus === RunStatus.paused) {
    return {
      level: "paused",
      labelKey: i.hitl ? "humanReviewWaiting" : "runPaused",
      tone: "amber",
      canSend: false,
      blocked: false,
    };
  }

  // 4. 运行中
  if (i.busy || i.runStatus === RunStatus.running) {
    return {
      level: "running",
      labelKey: "building",
      tone: "amber",
      canSend: false,
      blocked: false,
    };
  }

  // 5. 已完成（有可玩版本且空闲）
  if (i.previewUrl) {
    return {
      level: "completed",
      labelKey: "forgeStatusCompleted",
      tone: "emerald",
      canSend: true,
      blocked: false,
    };
  }

  // 6. 就绪 / 7. 未开始
  if (i.runStatus === "idle") {
    return {
      level: "idle",
      labelKey: "ready",
      tone: "slate",
      canSend: true,
      blocked: false,
    };
  }

  // runStatus === done（无版本回退，理论少见）
  return {
    level: "ready",
    labelKey: "ready",
    tone: "primary",
    canSend: true,
    blocked: false,
  };
}
