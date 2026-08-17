import { RunPhase } from "@/api/enums";
import { cn } from "@/lib/cn";
import {
  formatEtaSeconds,
  PHASE_HUMAN_LABEL_KEYS,
  PHASE_ETA_SECONDS,
  PIPELINE_PHASES,
} from "@/lib/phase-labels";
import type { StagePipelineState } from "@/lib/stage-pipeline-state";
import { useT } from "@/i18n/use-t";
import { Check, Circle, Loader2, X } from "lucide-react";

type Props = {
  runPhase: RunPhase | "idle" | "paused";
  stages: StagePipelineState;
  /** 列数（仅 variant=grid 生效）：默认 2；4 用于底部日志带的单行紧凑展示（窄屏回退 2 列） */
  columns?: 2 | 4;
  /** grid = 卡片网格（默认，日志带用）；bar = 44px 单行横条（Header 进度条用） */
  variant?: "grid" | "bar";
  className?: string;
};

const phaseTitleKeys = {
  [RunPhase.plan]: "phasePlan",
  [RunPhase.art]: "phaseArt",
  [RunPhase.code]: "phaseCode",
  [RunPhase.qa]: "phaseQa",
} as const;

export function StagePipeline({
  runPhase,
  stages,
  columns = 2,
  variant = "grid",
  className,
}: Props) {
  const t = useT();

  if (variant === "bar") {
    return (
      <ol
        className={cn("flex w-full items-center gap-2 px-8 md:px-12", className)}
        aria-label={t("generationFlow")}
      >
        {PIPELINE_PHASES.map((phase, index) => {
          const info = stages[phase];
          const titleKey = phaseTitleKeys[phase as keyof typeof phaseTitleKeys];
          const isActive =
            info.status === "active" ||
            (runPhase === phase &&
              info.status !== "done" &&
              info.status !== "failed");
          const StatusIcon =
            info.status === "failed"
              ? X
              : info.status === "done"
                ? Check
                : isActive
                  ? Loader2
                  : Circle;
          const isLast = index === PIPELINE_PHASES.length - 1;
          return (
            <li
              key={phase}
              aria-current={isActive ? "step" : undefined}
              className={cn(
                "flex items-center gap-1.5",
                isLast ? "shrink-0" : "min-w-0 flex-1",
              )}
            >
              <span
                className={cn(
                  "grid h-6 w-6 shrink-0 place-items-center rounded-full border",
                  info.status === "failed" &&
                    "border-rose-300 bg-rose-100 text-rose-700",
                  info.status === "done" &&
                    "border-emerald-300 bg-emerald-100 text-emerald-700",
                  isActive &&
                    info.status !== "failed" &&
                    "border-[rgba(var(--gf-primary-rgb),0.35)] bg-[rgba(var(--gf-primary-rgb),0.12)] gf-text-accent",
                  info.status === "pending" &&
                    !isActive &&
                    "gf-border-subtle bg-[var(--gf-surface)] gf-page-muted",
                )}
              >
                <StatusIcon
                  className={cn(
                    "h-3 w-3",
                    isActive && "animate-spin motion-reduce:animate-none",
                  )}
                  strokeWidth={2.2}
                  aria-hidden="true"
                />
              </span>
              <span
                className={cn(
                  "whitespace-nowrap text-[13px] font-semibold",
                  isActive ? "gf-page-body" : "gf-page-muted",
                )}
              >
                {t(titleKey)}
              </span>
              {!isLast ? (
                <span
                  className={cn(
                    "ml-auto h-px min-w-[8px] flex-1",
                    info.status === "done"
                      ? "bg-emerald-300/70"
                      : "bg-black/[0.08]",
                  )}
                />
              ) : null}
            </li>
          );
        })}
      </ol>
    );
  }

  const gridCols =
    columns === 4 ? "grid-cols-2 md:grid-cols-4" : "sm:grid-cols-2";

  return (
    <section
      className={cn("space-y-2", className)}
      aria-label={t("generationFlow")}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-medium uppercase tracking-[0.12em] gf-page-muted">
          {t("stagePipelineTitle")}
        </p>
        <span className="font-mono text-[11px] tabular-nums gf-page-muted">
          {
            PIPELINE_PHASES.filter((phase) => stages[phase].status === "done")
              .length
          }
          /{PIPELINE_PHASES.length}
        </span>
      </div>
      <ol className={cn("grid gap-2", gridCols)}>
        {PIPELINE_PHASES.map((phase, index) => {
          const info = stages[phase];
          const titleKey = phaseTitleKeys[phase as keyof typeof phaseTitleKeys];
          const human =
            info.humanLabel ??
            (info.status === "active" || info.status === "done"
              ? t(PHASE_HUMAN_LABEL_KEYS[phase])
              : t(PHASE_HUMAN_LABEL_KEYS[phase]));
          const etaSec = info.etaSeconds ?? PHASE_ETA_SECONDS[phase];
          const eta =
            info.status === "active" && etaSec > 0
              ? formatEtaSeconds(etaSec, t)
              : "";
          const isActive =
            info.status === "active" ||
            (runPhase === phase &&
              info.status !== "done" &&
              info.status !== "failed");
          const StatusIcon =
            info.status === "failed"
              ? X
              : info.status === "done"
                ? Check
                : isActive
                  ? Loader2
                  : Circle;
          return (
            <li
              key={phase}
              aria-current={isActive ? "step" : undefined}
              className={cn(
                "group relative rounded-xl border px-3 py-3 text-xs transition-[border-color,background-color,box-shadow]",
                info.status === "failed" &&
                  "border-rose-300/60 bg-rose-50/90 text-rose-900 shadow-sm",
                info.status === "done" &&
                  "border-emerald-300/40 bg-emerald-50/50 text-emerald-900",
                isActive &&
                  info.status !== "failed" &&
                  "border-[rgba(var(--gf-primary-rgb),0.4)] bg-[rgba(var(--gf-primary-rgb),0.08)] shadow-[0_0_0_1px_rgba(var(--gf-primary-rgb),0.06)]",
                info.status === "pending" &&
                  !isActive &&
                  "gf-border-subtle border bg-black/[0.018] gf-page-muted",
              )}
            >
              <div className="flex items-start gap-2.5">
                <span
                  className={cn(
                    "mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full border",
                    info.status === "failed" &&
                      "border-rose-300 bg-rose-100 text-rose-700",
                    info.status === "done" &&
                      "border-emerald-300 bg-emerald-100 text-emerald-700",
                    isActive &&
                      info.status !== "failed" &&
                      "border-[rgba(var(--gf-primary-rgb),0.3)] bg-[rgba(var(--gf-primary-rgb),0.12)] gf-text-accent",
                    info.status === "pending" &&
                      !isActive &&
                      "gf-border-subtle bg-[var(--gf-surface)] gf-page-muted",
                  )}
                >
                  <StatusIcon
                    className={cn(
                      "h-3 w-3",
                      isActive && "animate-spin motion-reduce:animate-none",
                    )}
                    strokeWidth={2.2}
                    aria-hidden="true"
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium gf-page-body">
                      {t(titleKey)}
                    </span>
                    <span className="font-mono text-[11px] tabular-nums opacity-55">
                      0{index + 1}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 leading-relaxed">{human}</p>
                  {eta ? (
                    <p className="mt-1 font-mono text-[11px] tabular-nums opacity-65">
                      {eta}
                    </p>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
