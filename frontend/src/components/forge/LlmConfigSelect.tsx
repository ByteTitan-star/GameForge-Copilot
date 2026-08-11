import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bot, ChevronDown, Loader2 } from "lucide-react";
import { formatApiError } from "@/api/error-message";
import { meApi } from "@/api/me";
import { pickDefaultLlmConfigId } from "@/lib/llm-config";
import { useT } from "@/i18n/use-t";
import { cn } from "@/lib/cn";

type Props = {
  accessToken: string;
  value: string | null;
  onChange: (configId: string | null) => void;
  disabled?: boolean;
  className?: string;
};

export function LlmConfigSelect({
  accessToken,
  value,
  onChange,
  disabled,
  className,
}: Props) {
  const t = useT();
  const q = useQuery({
    queryKey: ["llm-configs"],
    queryFn: () => meApi.listLlmConfigs(accessToken),
    enabled: Boolean(accessToken),
  });

  const configs = q.data ?? [];
  const defaultId = pickDefaultLlmConfigId(configs);
  const selected = value ?? defaultId;

  if (q.isLoading) {
    return (
      <p
        className={cn(
          "flex items-center gap-2 text-xs gf-page-muted",
          className,
        )}
      >
        <Loader2
          className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none"
          aria-hidden="true"
        />
        {t("loading")}
      </p>
    );
  }

  if (q.isError) {
    return (
      <div className={cn("text-xs text-rose-500", className)} role="alert">
        {t("llmConfigLoadFailed")} {formatApiError(q.error)}{" "}
        <Link to="/settings" className="underline-offset-2 hover:underline">
          {t("llmConfigGoSettings")}
        </Link>
      </div>
    );
  }

  if (configs.length === 0) {
    return (
      <div className={cn("text-xs", className)}>
        <span className="gf-page-muted">{t("llmConfigNone")}</span>{" "}
        <Link
          to="/settings"
          className="gf-text-accent underline-offset-2 hover:underline"
        >
          {t("llmConfigGoSettings")}
        </Link>
      </div>
    );
  }

  return (
    <label className={cn("flex min-w-0 items-center gap-2 text-xs", className)}>
      <span className="sr-only">{t("llmConfigSelect")}</span>
      <Bot
        className="h-4 w-4 shrink-0 text-[var(--gf-text-muted)]"
        aria-hidden="true"
      />
      <span className="relative min-w-0 flex-1">
        <select
          aria-label={t("llmConfigSelect")}
          value={selected ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value || null)}
          className="gf-border-subtle h-9 w-full min-w-0 cursor-pointer appearance-none truncate rounded-lg border bg-[var(--gf-surface)] py-1.5 pr-8 pl-2.5 gf-page-body outline-none transition-[border-color,box-shadow] focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.35)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {configs.map((c) => (
            <option key={c.config_id} value={c.config_id}>
              {c.provider} · {c.model}
              {c.is_default ? ` (${t("llmDefault")})` : ""}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute top-1/2 right-2.5 h-3.5 w-3.5 -translate-y-1/2 text-[var(--gf-text-muted)]"
          aria-hidden="true"
        />
      </span>
    </label>
  );
}
