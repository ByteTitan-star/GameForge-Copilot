import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useT } from "@/i18n/use-t";
import { cn } from "@/lib/cn";

const STORAGE_KEY = "gf-forge-stage-ratio";
const DEFAULT_STAGE_RATIO = 0.64;
const MIN_STAGE_RATIO = 0.55;
const MAX_STAGE_RATIO = 0.72;
const MIN_LEFT_PX = 320;

type Props = {
  stageOpen: boolean;
  left: ReactNode;
  right: ReactNode;
  className?: string;
  /** 移动端（<lg）视图切换：chat=只看聊天，play=只试试玩；桌面端忽略 */
  mobileView?: "chat" | "play";
  onMobileViewChange?: (view: "chat" | "play") => void;
};

function readStoredRatio(): number {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STAGE_RATIO;
    const n = Number(raw);
    if (!Number.isFinite(n)) return DEFAULT_STAGE_RATIO;
    return Math.min(MAX_STAGE_RATIO, Math.max(MIN_STAGE_RATIO, n));
  } catch {
    return DEFAULT_STAGE_RATIO;
  }
}

export function ForgeSplitLayout({
  stageOpen,
  left,
  right,
  className,
  mobileView = "chat",
  onMobileViewChange,
}: Props) {
  const t = useT();
  const containerRef = useRef<HTMLDivElement>(null);
  const [stageRatio, setStageRatio] = useState(readStoredRatio);
  const draggingRef = useRef(false);

  const persistRatio = useCallback((ratio: number) => {
    const clamped = Math.min(MAX_STAGE_RATIO, Math.max(MIN_STAGE_RATIO, ratio));
    setStageRatio(clamped);
    try {
      localStorage.setItem(STORAGE_KEY, String(clamped));
    } catch {
      /* ignore quota errors */
    }
  }, []);

  useEffect(() => {
    if (!stageOpen) return;

    function onPointerMove(event: PointerEvent) {
      if (!draggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const usable = rect.width - 12;
      if (usable <= 0) return;
      const leftWidth = event.clientX - rect.left;
      const leftRatio = leftWidth / usable;
      const nextStageRatio = 1 - leftRatio;
      if (leftWidth < MIN_LEFT_PX) return;
      persistRatio(nextStageRatio);
    }

    function onPointerUp() {
      draggingRef.current = false;
      document.body.classList.remove("gf-forge-resizing");
    }

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      document.body.classList.remove("gf-forge-resizing");
    };
  }, [persistRatio, stageOpen]);

  const leftRatio = `${((1 - stageRatio) * 100).toFixed(2)}%`;

  function resizeWithKeyboard(event: KeyboardEvent<HTMLDivElement>) {
    const step = event.shiftKey ? 0.05 : 0.02;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      persistRatio(stageRatio + step);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      persistRatio(stageRatio - step);
    } else if (event.key === "Home") {
      event.preventDefault();
      persistRatio(MAX_STAGE_RATIO);
    } else if (event.key === "End") {
      event.preventDefault();
      persistRatio(MIN_STAGE_RATIO);
    }
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "gf-forge-split flex h-full min-h-0 flex-col gap-3 lg:grid lg:gap-0",
        stageOpen && "gf-forge-split--stage-open",
        className,
      )}
      style={
        stageOpen
          ? ({
              gridTemplateColumns: `${leftRatio} 6px 1fr`,
            } as CSSProperties)
          : // 关闭预览时显式单列填满，避免 grid 退到 auto 隐式列导致面板宽度不确定/溢出
            ({
              gridTemplateColumns: "minmax(0, 1fr)",
            } as CSSProperties)
      }
    >
      {onMobileViewChange ? (
        <div
          role="tablist"
          aria-label={t("forge")}
          className="flex shrink-0 items-center gap-1 rounded-lg border border-black/[0.06] bg-black/[0.03] p-1 lg:hidden"
        >
          <button
            type="button"
            role="tab"
            aria-selected={mobileView === "chat"}
            onClick={() => onMobileViewChange("chat")}
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              mobileView === "chat"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#64748B] hover:text-[#0F172A]",
            )}
          >
            {t("chat")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mobileView === "play"}
            onClick={() => onMobileViewChange("play")}
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              mobileView === "play"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#64748B] hover:text-[#0F172A]",
            )}
          >
            {t("playView")}
          </button>
        </div>
      ) : null}

      <div
        className={cn(
          "gf-forge-panel-left flex flex-col min-h-0 min-w-0",
          mobileView === "play" && "max-lg:hidden",
        )}
      >
        {left}
      </div>

      {stageOpen || mobileView === "play" ? (
        <>
          <div
            role="separator"
            aria-orientation="vertical"
            aria-valuenow={Math.round(stageRatio * 100)}
            aria-valuemin={Math.round(MIN_STAGE_RATIO * 100)}
            aria-valuemax={Math.round(MAX_STAGE_RATIO * 100)}
            tabIndex={0}
            aria-label={t("forgeDragToResize")}
            title={t("forgeDragToResize")}
            className="gf-forge-split-handle group relative hidden cursor-col-resize touch-none place-items-center outline-none focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.4)] focus-visible:ring-offset-2 xl:grid"
            onPointerDown={(event) => {
              event.preventDefault();
              draggingRef.current = true;
              document.body.classList.add("gf-forge-resizing");
            }}
            onKeyDown={resizeWithKeyboard}
          />
          <div
            className={cn(
              "gf-forge-panel-right flex flex-col min-h-0 min-w-0",
              mobileView === "chat" && "max-lg:hidden",
            )}
          >
            {right}
          </div>
        </>
      ) : null}
    </div>
  );
}
