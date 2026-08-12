import { ArrowUpRight, Gamepad2, Heart, Users } from "lucide-react";
import { useT } from "@/i18n/use-t";
import { cn } from "@/lib/cn";

const chips = [
  {
    key: "retroShooter",
    promptKey: "retroShooterPrompt",
    icon: Gamepad2,
  },
  {
    key: "coopAdventure",
    promptKey: "coopAdventurePrompt",
    icon: Users,
  },
  {
    key: "cozyCollection",
    promptKey: "cozyCollectionPrompt",
    icon: Heart,
  },
] as const;

type Props = {
  onPick: (text: string) => void;
  className?: string;
};

export function ForgeQuickTemplates({ onPick, className }: Props) {
  const t = useT();

  return (
    <div className={cn("space-y-2", className)}>
      <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--gf-text-muted)]">
        {t("quickTemplates")}
      </p>
      <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1 2xl:grid-cols-3">
        {chips.map(({ key, promptKey, icon: Icon }) => {
          const label = t(key);
          return (
            <button
              key={key}
              type="button"
              onClick={() => onPick(t(promptKey))}
              className={cn(
                "gf-forge-template-chip gf-interactive group flex min-h-11 cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left text-sm text-[var(--gf-text)] transition-[border-color,background-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-[rgba(var(--gf-primary-rgb),0.28)] hover:bg-[rgba(var(--gf-primary-rgb),0.05)] hover:shadow-sm focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.3)] motion-reduce:transform-none",
              )}
            >
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-black/[0.035] transition-colors group-hover:bg-[rgba(var(--gf-primary-rgb),0.1)]">
                <Icon
                  className="h-4 w-4 text-[var(--gf-text-muted)] group-hover:text-[var(--gf-primary)]"
                  aria-hidden="true"
                />
              </span>
              <span className="min-w-0 flex-1 truncate">{label}</span>
              <ArrowUpRight
                className="h-3.5 w-3.5 shrink-0 text-[var(--gf-text-muted)] opacity-0 transition-opacity group-hover:opacity-100"
                aria-hidden="true"
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
