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
const DEFAULT_STAGE_RATIO = 0.62;
const MIN_STAGE_RATIO = 0.45;
const MAX_STAGE_RATIO = 0.72;
const MIN_LEFT_PX = 360;

type Props = {
  stageOpen: boolean;
  left: ReactNode;
  right: ReactNode;
  className?: string;
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

export function ForgeSplitLayout({ stageOpen, left, right, className }: Props) {
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
  const rightRatio = `${(stageRatio * 100).toFixed(2)}%`;

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
              "--gf-forge-left-ratio": leftRatio,
              gridTemplateColumns: `${leftRatio} 12px minmax(0, ${rightRatio})`,
            } as CSSProperties)
          : undefined
      }
    >
      <div className="gf-forge-panel-left min-h-[420px] lg:min-h-0">{left}</div>

      {stageOpen ? (
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
            className="gf-forge-split-handle group relative hidden cursor-col-resize touch-none place-items-center outline-none focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.4)] focus-visible:ring-offset-2 lg:grid"
            onPointerDown={(event) => {
              event.preventDefault();
              draggingRef.current = true;
              document.body.classList.add("gf-forge-resizing");
            }}
            onKeyDown={resizeWithKeyboard}
          />
          <div className="gf-forge-panel-right min-h-[480px] lg:min-h-0">
            {right}
          </div>
        </>
      ) : null}
    </div>
  );
}
