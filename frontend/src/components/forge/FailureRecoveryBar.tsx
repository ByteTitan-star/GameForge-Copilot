import { useState } from "react";
import {
  AlertOctagon,
  Copy,
  Loader2,
  Mail,
  MessageSquare,
  RotateCcw,
  Settings,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { submitFeedback } from "@/api/feedback";
import { formatApiError } from "@/api/error-message";
import { useAuthStore } from "@/stores/auth-store";
import { toast } from "@/stores/toast-store";
import { useT } from "@/i18n/use-t";
import { cn } from "@/lib/cn";

type Props = {
  runId: string;
  errorSummary?: string;
  onRevise: () => void;
  onRetry: () => void;
  busy?: boolean;
  /** 失败原因分类：llm = LLM 配置缺失/无效（主操作变为「去配置」）；generic = 其他失败 */
  kind?: "llm" | "generic";
  onConfigureLlm?: () => void;
  className?: string;
};

export function FailureRecoveryBar({
  runId,
  errorSummary,
  onRevise,
  onRetry,
  busy,
  kind = "generic",
  onConfigureLlm,
  className,
}: Props) {
  const t = useT();
  const token = useAuthStore((s) => s.access_token);
  const isLlm = kind === "llm";

  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function copyRunId() {
    try {
      await navigator.clipboard.writeText(runId);
    } catch {
      /* ignore */
    }
  }

  function openFeedback() {
    setMessage("");
    setFeedbackOpen(true);
  }

  async function sendFeedback() {
    setFeedbackBusy(true);
    try {
      await submitFeedback(
        {
          run_id: runId,
          message,
          error_summary: errorSummary ?? "",
        },
        token ?? "",
      );
      toast.success(t("feedbackSent"));
      setFeedbackOpen(false);
    } catch (e) {
      toast.error(formatApiError(e, t("feedbackFailed")));
    } finally {
      setFeedbackBusy(false);
    }
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
        {isLlm ? (
          <Button
            type="button"
            variant="ghost"
            className="!min-h-10 !rounded-lg !bg-rose-600 !px-3 !text-xs !text-white hover:!bg-rose-700"
            onClick={onConfigureLlm}
          >
            <Settings className="h-3.5 w-3.5" />
            {t("forgeConfigureLlm")}
          </Button>
        ) : (
          <>
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
          </>
        )}
        <Button
          type="button"
          variant="ghost"
          className="!min-h-10 !rounded-lg !px-3 !text-xs !text-rose-800 hover:!bg-rose-50"
          onClick={openFeedback}
        >
          <Mail className="h-3.5 w-3.5" />
          {t("failureContact")}
        </Button>
      </div>

      {feedbackOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <button
            type="button"
            aria-label={t("close")}
            className="absolute inset-0 cursor-pointer bg-black/40"
            onClick={() => (feedbackBusy ? undefined : setFeedbackOpen(false))}
          />
          <div
            role="dialog"
            aria-modal
            aria-label={t("feedbackTitle")}
            className="relative w-full max-w-md rounded-2xl border border-rose-200 bg-white p-5 shadow-xl"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-rose-950">
                {t("feedbackTitle")}
              </h3>
              <button
                type="button"
                aria-label={t("close")}
                disabled={feedbackBusy}
                onClick={() => setFeedbackOpen(false)}
                className="rounded p-0.5 text-rose-400 transition hover:text-rose-700 disabled:opacity-40"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              maxLength={2000}
              rows={4}
              placeholder={t("feedbackPlaceholder")}
              disabled={feedbackBusy}
              className="mt-3 w-full resize-none rounded-lg border border-rose-200 bg-rose-50/40 px-3 py-2 text-sm text-rose-950 placeholder:text-rose-400 focus:border-rose-400 focus:outline-none focus:ring-2 focus:ring-rose-200 disabled:opacity-60"
            />
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                className="!min-h-9 !rounded-lg !px-3 !text-xs !text-rose-800 hover:!bg-rose-50"
                disabled={feedbackBusy}
                onClick={() => setFeedbackOpen(false)}
              >
                {t("feedbackCancel")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="!min-h-9 !rounded-lg !bg-rose-600 !px-3 !text-xs !text-white hover:!bg-rose-700"
                disabled={feedbackBusy}
                onClick={() => void sendFeedback()}
              >
                {feedbackBusy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
                ) : (
                  <Mail className="h-3.5 w-3.5" />
                )}
                {t("feedbackSend")}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
