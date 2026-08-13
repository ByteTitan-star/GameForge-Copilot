import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { fetchDraftHtml } from "@/lib/hosting";
import { useT } from "@/i18n/use-t";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  src: string;
  title?: string;
  variant?: "light" | "console" | "stage";
  className?: string;
  /** 草稿托管需 Bearer；iframe 无法带头，内部改为 fetch→blob */
  accessToken?: string | null;
};

function isDraftUrl(src: string): boolean {
  return /\/draft\//.test(src);
}

/** 试玩容器：sandbox 不含 allow-same-origin（对齐 docs/08） */
export function GamePlayer({
  src,
  title = "Game preview",
  variant = "light",
  className,
  accessToken,
}: Props) {
  const console = variant === "console";
  const stage = variant === "stage";
  const needsInitialAuthFetch = isDraftUrl(src) && Boolean(accessToken);
  const [iframeSrc, setIframeSrc] = useState(() =>
    needsInitialAuthFetch ? "" : src,
  );
  const [iframeHtml, setIframeHtml] = useState("");
  const [error, setError] = useState<string | null>(null);
  // 公开地址可直接挂载；受保护草稿必须等 Bearer fetch 转成 blob 后再挂载。
  const [loading, setLoading] = useState(needsInitialAuthFetch);
  const [retryVersion, setRetryVersion] = useState(0);
  const t = useT();

  useEffect(() => {
    let cancelled = false;
    // 兜底：跨域 iframe 的 onLoad 在外部 CDN（字体等）慢时可能迟迟不触发，
    // 8s 后强制关 loading，避免一直转圈把用户挡在外面。
    const fallbackTimer = window.setTimeout(() => {
      if (!cancelled) setLoading(false)
    }, 8000)

    async function load() {
      setError(null);
      const needsAuthFetch = isDraftUrl(src) && Boolean(accessToken);
      if (!needsAuthFetch) {
        setIframeHtml("");
        setIframeSrc(src);
        setLoading(false);
        return;
      }
      // 不能先把受保护的 draft URL 交给 iframe；iframe 无法附带 Bearer，
      // 会制造一次必然 401 的请求。先鉴权 fetch，完成后只挂载 blob URL。
      setIframeSrc("");
      setIframeHtml("");
      setLoading(true);
      try {
        const match = src.match(/\/draft\/([^/]+)\/([^/?#]+)/);
        if (!match) throw new Error("草稿地址无效");
        const html = await fetchDraftHtml(
          decodeURIComponent(match[1]),
          decodeURIComponent(match[2]),
          accessToken!,
        );
        if (!cancelled) {
          setIframeHtml(html);
          // srcDoc 不依赖 Blob URL 生命周期，避免 HMR/effect cleanup 撤销正在
          // 加载的文档。sandbox 仍不含 allow-same-origin，隔离级别不变。
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) {
          setLoading(false);
          setError(e instanceof Error ? e.message : t("loadFailed"));
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
      window.clearTimeout(fallbackTimer);
    };
  }, [src, accessToken, retryVersion]);

  return (
    <div
      className={cn(
        "overflow-hidden",
        stage
          ? "relative h-full w-full rounded-xl bg-white ring-1 ring-black/[0.08]"
          : console
            ? "h-full rounded-xl border border-white/[0.08] bg-black/40"
            : "rounded-2xl border border-[rgba(30,50,90,0.1)] bg-white shadow-sm",
        className,
      )}
    >
      {!stage ? (
        <div
          className={cn(
            "border-b px-4 py-2 text-xs",
            console
              ? "border-white/[0.06] font-mono text-white/45"
              : "border-[rgba(30,50,90,0.08)] text-[rgba(30,50,90,0.55)]",
          )}
        >
          {title}
        </div>
      ) : null}
      {error ? (
        <div
          className="grid h-full min-h-[280px] place-items-center p-6 text-center"
          role="alert"
        >
          <div className="max-w-sm">
            <span className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-rose-50 text-rose-600 ring-1 ring-rose-200">
              <AlertCircle className="h-5 w-5" aria-hidden="true" />
            </span>
            <p className="mt-3 text-sm font-medium text-[#0F172A]">
              {t("loadFailed")}
            </p>
            <p className="mt-1 break-words text-xs leading-relaxed text-[#94A3B8]">
              {error}
            </p>
            <Button
              variant="ghost"
              className="mt-4 !min-h-10 !rounded-lg !bg-black/[0.04] !px-3 !text-xs !text-[#0F172A] hover:!bg-black/[0.08]"
              onClick={() => setRetryVersion((version) => version + 1)}
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              {t("failureRetry")}
            </Button>
          </div>
        </div>
      ) : (
        <>
          {loading ? (
            <div
              className="pointer-events-none absolute inset-0 z-10 grid place-items-center bg-white/80"
              aria-live="polite"
            >
              <div className="flex items-center gap-2 rounded-lg bg-black/[0.03] px-3 py-2 text-xs text-[#64748B] ring-1 ring-black/[0.08]">
                <Loader2
                  className="h-3.5 w-3.5 animate-spin text-[#0F172A] motion-reduce:animate-none"
                  aria-hidden="true"
                />
                {t("loading")}
              </div>
            </div>
          ) : null}
          {iframeSrc || iframeHtml ? (
            <iframe
              title={title}
              src={iframeSrc || undefined}
              srcDoc={iframeHtml || undefined}
              sandbox="allow-scripts"
              loading="eager"
              referrerPolicy="no-referrer"
              onLoad={() => setLoading(false)}
              className={cn(
                "w-full bg-white",
                stage
                  ? "h-full min-h-0"
                  : console
                    ? "h-[calc(100%-2.25rem)] min-h-[280px]"
                    : "h-[70vh]",
              )}
            />
          ) : null}
        </>
      )}
    </div>
  );
}
