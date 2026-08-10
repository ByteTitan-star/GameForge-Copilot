import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useToastStore, type ToastType } from "@/stores/toast-store";
import { useT } from "@/i18n/use-t";
import { cn } from "@/lib/cn";

const STYLES: Record<ToastType, string> = {
  error: "border-rose-200 bg-rose-50 text-rose-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  info: "border-slate-200 bg-white text-slate-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
};

/**
 * 全局瞬时提示。createPortal 挂 document.body + fixed 定位，
 * 彻底脱离页面 flex 文档流，不挤占任何组件。
 */
export function Toaster() {
  const t = useT();
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  if (typeof document === "undefined") return null;
  return createPortal(
    <div
      className="pointer-events-none fixed top-4 right-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2"
      role="region"
      aria-label={t("notifications")}
    >
      {toasts.map((item) => (
        <div
          key={item.id}
          role={item.type === "error" ? "alert" : "status"}
          aria-live={item.type === "error" ? "assertive" : "polite"}
          className={cn(
            "gf-toast-in pointer-events-auto flex items-start gap-2 rounded-xl border px-3 py-2.5 text-sm shadow-md",
            STYLES[item.type],
          )}
        >
          <span className="min-w-0 flex-1 break-words">{item.message}</span>
          <button
            type="button"
            onClick={() => dismiss(item.id)}
            aria-label={t("close")}
            className="shrink-0 rounded p-0.5 opacity-60 transition hover:opacity-100"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>,
    document.body,
  );
}
