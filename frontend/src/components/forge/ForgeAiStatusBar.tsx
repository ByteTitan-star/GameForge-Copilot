import { Bot, Loader2, Sparkles } from "lucide-react";
import { useT } from "@/i18n/use-t";
import { cn } from "@/lib/cn";

type Props = {
  busy: boolean;
  className?: string;
};

export function ForgeAiStatusBar({ busy, className }: Props) {
  const t = useT();

  return (
    <div
      className={cn(
        "gf-forge-ai-bar flex shrink-0 items-center gap-3 border-b px-4 py-3",
        className,
      )}
      aria-live="polite"
    >
      <span className="relative grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[rgba(var(--gf-primary-rgb),0.1)] ring-1 ring-[rgba(var(--gf-primary-rgb),0.18)]">
        {busy ? (
          <Loader2
            className="gf-text-accent h-4.5 w-4.5 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
        ) : (
          <Bot
            className="gf-text-accent h-4.5 w-4.5"
            strokeWidth={1.7}
            aria-hidden="true"
          />
        )}
        <span
          className={cn(
            "absolute -right-0.5 -bottom-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-[var(--gf-surface)]",
            busy
              ? "animate-pulse bg-amber-400 motion-reduce:animate-none"
              : "bg-emerald-500",
          )}
          aria-hidden
        />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--gf-text-muted)]">
          {t("requirementChat")}
        </p>
        <p className="mt-0.5 truncate text-sm font-medium text-[var(--gf-text)]">
          {busy ? t("forgeAiBuilding") : t("forgeAiReady")}
        </p>
      </div>
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-black/[0.03]">
        <Sparkles
          className="gf-text-accent h-4 w-4 opacity-80"
          aria-hidden="true"
        />
      </span>
    </div>
  );
}
