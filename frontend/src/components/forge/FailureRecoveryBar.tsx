import {
  AlertOctagon,
  Copy,
  Loader2,
  Mail,
  MessageSquare,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n/use-t";
import { cn } from "@/lib/cn";

type Props = {
  runId: string;
  errorSummary?: string;
  onRevise: () => void;
  onRetry: () => void;
  busy?: boolean;
  className?: string;
};

export function FailureRecoveryBar({
  runId,
  errorSummary,
  onRevise,
  onRetry,
  busy,
  className,
}: Props) {
  const t = useT();
  const supportEmail =
    import.meta.env.VITE_SUPPORT_EMAIL ?? "support@gameforge.local";

  async function copyRunId() {
    try {
      await navigator.clipboard.writeText(runId);
    } catch {
      /* ignore */
    }
  }

  function contactAdmin() {
    void copyRunId();
    const subject = encodeURIComponent(`GameForge run ${runId}`);
    const body = encodeURIComponent(
      `${errorSummary ? `Error: ${errorSummary}\n\n` : ""}run_id: ${runId}`,
    );
    window.location.href = `mailto:${supportEmail}?subject=${subject}&body=${body}`;
  }

  return (
    <section
      className={cn(
        "rounded-2xl border border-rose-200 bg-white px-4 py-4 text-rose-950 shadow-sm",
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-rose-50 text-rose-600 ring-1 ring-rose-200">
          <AlertOctagon className="h-4.5 w-4.5" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{t("failureRecoveryTitle")}</p>
          {errorSummary ? (
            <p className="mt-1 break-words text-xs leading-relaxed text-rose-800/80">
              {errorSummary}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => void copyRunId()}
            className="mt-2 inline-flex min-h-7 max-w-full items-center gap-1.5 rounded-md bg-rose-50 px-2 font-mono text-[10px] text-rose-700 transition-colors hover:bg-rose-100 focus-visible:ring-2 focus-visible:ring-rose-300"
            title={runId}
          >
            <Copy className="h-3 w-3" aria-hidden="true" />
            <span className="truncate">{runId}</span>
          </button>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-rose-100 pt-3">
        <Button
          type="button"
          variant="ghost"
          className="!min-h-10 !rounded-lg !px-3 !text-xs !text-rose-800 hover:!bg-rose-50"
          disabled={busy}
          onClick={onRevise}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          {t("failureRevise")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="!min-h-10 !rounded-lg !bg-rose-600 !px-3 !text-xs !text-white hover:!bg-rose-700"
          disabled={busy}
          onClick={onRetry}
        >
          {busy ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
          ) : (
            <RotateCcw className="h-3.5 w-3.5" />
          )}
          {t("failureRetry")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="!min-h-10 !rounded-lg !px-3 !text-xs !text-rose-800 hover:!bg-rose-50"
          onClick={contactAdmin}
        >
          <Mail className="h-3.5 w-3.5" />
          {t("failureContact")}
        </Button>
      </div>
    </section>
  );
}
