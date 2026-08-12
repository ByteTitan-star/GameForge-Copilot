import { cn } from "@/lib/cn";
import { RunPhase } from "@/api/enums";
import { useT } from "@/i18n/use-t";
import { AlertTriangle, Check, Circle, Info, X } from "lucide-react";

export type TimelineItem = {
  id: string;
  label: string;
  detail?: string;
  tone: "info" | "ok" | "warn" | "err" | "muted";
  at: string;
};

const PHASES: RunPhase[] = [
  RunPhase.plan,
  RunPhase.art,
  RunPhase.code,
  RunPhase.qa,
  RunPhase.done,
];

type Props = {
  phase: RunPhase | "idle" | "paused";
  items: TimelineItem[];
  /** 是否渲染内置的「生成流程 + 阶段 chips」表头；底部日志带已在外层展示 StagePipeline，传 false 去重 */
  showHeader?: boolean;
  /** 是否由本组件承担滚动。默认 true（独立面板使用）；底部日志带把进度条与事件流放进同一外层
   * 滚动容器时传 false，避免双层滚动嵌套，列表高度自适应、由外层统一滚动。 */
  scrollable?: boolean;
  className?: string;
};

const toneClass: Record<
  TimelineItem["tone"],
  { dot: string; icon: typeof Circle }
> = {
  info: {
    dot: "border-[#5271ff]/30 bg-[#5271ff]/10 text-[#4057cc]",
    icon: Info,
  },
  ok: { dot: "border-emerald-300 bg-emerald-50 text-emerald-700", icon: Check },
  warn: {
    dot: "border-amber-300 bg-amber-50 text-amber-700",
    icon: AlertTriangle,
  },
  err: { dot: "border-rose-300 bg-rose-50 text-rose-700", icon: X },
  muted: {
    dot: "border-black/10 bg-black/[0.03] text-[#69737c]",
    icon: Circle,
  },
};

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export function RunTimeline({
  phase,
  items,
  showHeader = true,
  scrollable = true,
  className,
}: Props) {
  const t = useT();
  const phaseLabels: Record<RunPhase, string> = {
    [RunPhase.plan]: t("phasePlan"),
    [RunPhase.art]: t("phaseArt"),
    [RunPhase.code]: t("phaseCode"),
    [RunPhase.qa]: t("phaseQa"),
    [RunPhase.done]: t("phaseDone"),
  };
  const activeIdx = PHASES.indexOf(phase as RunPhase);

  return (
    <section
      className={cn(
        "flex flex-col overflow-hidden rounded-2xl border border-black/[0.08] bg-white",
        scrollable ? "h-full min-h-0" : "h-auto",
        className,
      )}
    >
      {showHeader ? (
        <header className="border-b border-black/[0.07] px-4 py-3">
          <p className="text-sm font-medium text-[#20262d]">
            {t("generationFlow")}
          </p>
          <ol className="mt-3 flex flex-wrap gap-1.5">
            {PHASES.map((p, i) => {
              const done = activeIdx > i || phase === RunPhase.done;
              const current =
                phase === p ||
                (phase === "paused" && p === RunPhase.plan && activeIdx <= 0);
              return (
                <li
                  key={p}
                  className={cn(
                    "rounded-md px-2 py-1 text-[11px] font-medium uppercase tracking-wider ring-1",
                    done && "bg-[#1b9a6c]/12 text-[#167052] ring-[#1b9a6c]/25",
                    current &&
                      !done &&
                      "bg-[#5271ff]/12 text-[#3046a8] ring-[#5271ff]/25",
                    !done &&
                      !current &&
                      "bg-black/[0.03] text-[#9099a1] ring-black/10",
                    phase === "paused" &&
                      p === RunPhase.plan &&
                      "bg-[#ffcf5a]/20 text-[#785d14] ring-[#d49d12]/25",
                  )}
                >
                  {phaseLabels[p]}
                </li>
              );
            })}
          </ol>
        </header>
      ) : null}

      <div className={cn("flex-1 px-3 py-3", scrollable ? "overflow-y-auto" : "overflow-visible")}>
        {items.length === 0 ? (
          <p className="px-1 py-8 text-center text-sm text-[#9099a1]">
            {t("timelineEmpty")}
          </p>
        ) : (
          <ol className="space-y-0.5">
            {items.slice(0, 50).map((it, index) => {
              const tone = toneClass[it.tone];
              const ToneIcon = tone.icon;
              return (
                <li
                  key={it.id}
                  className="group relative flex gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-black/[0.025]"
                >
                  {index < Math.min(items.length, 50) - 1 ? (
                    <span
                      className="absolute top-8 bottom-[-4px] left-[19px] w-px bg-black/[0.07]"
                      aria-hidden="true"
                    />
                  ) : null}
                  <span
                    className={cn(
                      "relative z-[1] grid h-6 w-6 shrink-0 place-items-center rounded-full border",
                      tone.dot,
                    )}
                  >
                    <ToneIcon className="h-3 w-3" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-3">
                      <p className="break-words text-sm font-medium text-[#303940]">
                        {it.label}
                      </p>
                      <time className="shrink-0 font-mono text-[11px] tabular-nums text-[#7f8992]">
                        {timeFormatter.format(new Date(it.at))}
                      </time>
                    </div>
                    {it.detail ? (
                      <p className="mt-0.5 break-words text-xs leading-relaxed text-[#69737c]">
                        {it.detail}
                      </p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
}
