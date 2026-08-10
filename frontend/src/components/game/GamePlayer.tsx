import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
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
  const [iframeSrc, setIframeSrc] = useState(src);
  const [error, setError] = useState<string | null>(null);
  // 初始即显示 iframe：跨域/sandbox 下 onLoad 可能不触发，避免 loading 覆盖层永久挡住内容
  const [loading, setLoading] = useState(false);
  const [retryVersion, setRetryVersion] = useState(0);
  const t = useT();

  useEffect(() => {
    let revoked: string | null = null;
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
        setIframeSrc(src);
        return;
      }
      try {
        const res = await fetch(src, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
            Accept: "text/html",
          },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const html = await res.text();
        const blobUrl = URL.createObjectURL(
          new Blob([html], { type: "text/html" }),
        );
        revoked = blobUrl;
        if (!cancelled) setIframeSrc(blobUrl);
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
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [src, accessToken, retryVersion, t]);

  return (
    <div
      className={cn(
        "overflow-hidden",
        stage
          ? "relative h-full w-full rounded-xl bg-[#090b10] ring-1 ring-white/10"
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
            <span className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-rose-500/10 text-rose-400 ring-1 ring-rose-400/20">
              <AlertCircle className="h-5 w-5" aria-hidden="true" />
            </span>
            <p className="mt-3 text-sm font-medium text-white">
              {t("loadFailed")}
            </p>
            <p className="mt-1 break-words text-xs leading-relaxed text-white/55">
              {error}
            </p>
            <Button
              variant="ghost"
              className="mt-4 !min-h-10 !rounded-lg !bg-white/8 !px-3 !text-xs !text-white hover:!bg-white/12"
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
              className="pointer-events-none absolute inset-0 z-10 grid place-items-center bg-[#090b10]"
              aria-live="polite"
            >
              <div className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2 text-xs text-white/60 ring-1 ring-white/10">
                <Loader2
                  className="h-3.5 w-3.5 animate-spin text-white/75 motion-reduce:animate-none"
                  aria-hidden="true"
                />
                {t("loading")}
              </div>
            </div>
          ) : null}
          <iframe
            title={title}
            src={iframeSrc}
            sandbox="allow-scripts"
            loading="eager"
            referrerPolicy="no-referrer"
            onLoad={() => setLoading(false)}
            className={cn(
              "w-full bg-[#111]",
              stage
                ? "h-full min-h-0"
                : console
                  ? "h-[calc(100%-2.25rem)] min-h-[280px]"
                  : "h-[70vh]",
            )}
          />
        </>
      )}
    </div>
  );
}
