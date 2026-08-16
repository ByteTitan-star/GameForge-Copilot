import { ArrowUp } from "lucide-react";
import { useEffect, useId, useRef } from "react";
import { cn } from "@/lib/cn";
import { useT } from "@/i18n/use-t";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  sendDisabled?: boolean;
  placeholder: string;
  className?: string;
  /** empty = 空态主轴；chat = 对话底栏 */
  density?: "empty" | "chat";
};

const MAX_LINES = 5;
const LINE_HEIGHT = 1.5;
const FONT_PX = 15;

/** Forge 共用极简 Composer：空态与对话态同一套发送逻辑外壳 */
export function ForgeComposer({
  value,
  onChange,
  onSend,
  disabled,
  sendDisabled,
  placeholder,
  className,
  density = "chat",
}: Props) {
  const t = useT();
  const id = useId();
  const ref = useRef<HTMLTextAreaElement>(null);
  const maxPx = FONT_PX * LINE_HEIGHT * MAX_LINES;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxPx)}px`;
  }, [value, maxPx]);

  const cannotSend = sendDisabled ?? (disabled || !value.trim());

  return (
    <div
      className={cn(
        "gf-forge-composer flex items-end gap-2 outline outline-1 outline-[rgba(15,23,42,0.07)] transition-[outline-color,box-shadow] focus-within:outline-[rgba(var(--gf-primary-rgb),0.4)] focus-within:shadow-[0_0_0_3px_rgba(var(--gf-primary-rgb),0.1)]",
        density === "empty"
          ? "rounded-3xl bg-[var(--gf-surface)] px-[18px] py-2.5 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_10px_32px_rgba(15,23,42,0.055)]"
          : "rounded-[22px] bg-black/[0.025] px-3.5 py-2",
        className,
      )}
    >
      <label htmlFor={id} className="sr-only">
        {placeholder}
      </label>
      <textarea
        ref={ref}
        id={id}
        name="forge-requirement"
        autoComplete="off"
        rows={1}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (!cannotSend) onSend();
          }
        }}
        className={cn(
          "gf-forge-composer-input min-w-0 flex-1 resize-none bg-transparent py-2 text-[15px] leading-[1.5] text-[var(--gf-text)] outline-none placeholder:text-[#94a3b8] disabled:opacity-50",
          "overflow-y-auto [scrollbar-width:thin] [scrollbar-color:transparent_transparent] hover:[scrollbar-color:rgba(15,23,42,0.16)_transparent] focus:[scrollbar-color:rgba(15,23,42,0.16)_transparent]",
        )}
        style={{ maxHeight: maxPx }}
      />
      <button
        type="button"
        aria-label={t("sendRequirement")}
        disabled={cannotSend}
        onClick={onSend}
        className={cn(
          "gf-forge-composer-send grid h-9 w-9 shrink-0 place-items-center self-end rounded-full text-white transition-[opacity,transform,filter] disabled:cursor-not-allowed disabled:bg-[#94a3b8] disabled:opacity-35 disabled:shadow-none",
          "bg-[linear-gradient(135deg,var(--gf-secondary),var(--gf-primary))] shadow-[0_0_14px_rgba(var(--gf-primary-rgb),0.22)]",
          "hover:enabled:brightness-105 active:enabled:scale-95",
        )}
      >
        <ArrowUp className="h-4 w-4" strokeWidth={2.4} aria-hidden="true" />
      </button>
    </div>
  );
}
