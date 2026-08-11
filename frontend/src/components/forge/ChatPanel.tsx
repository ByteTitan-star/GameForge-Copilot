import { Bot, Send, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { useT } from "@/i18n/use-t";
import { useId, type ReactNode } from "react";

export type ChatMsg = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
};

type Props = {
  messages: ChatMsg[];
  input: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
  /** 发送按钮禁用态，默认 = disabled || 输入为空；阻塞态可额外禁用 */
  sendDisabled?: boolean;
  streaming?: boolean;
  placeholder?: string;
  className?: string;
  showComposer?: boolean;
  /** workshop = 浅色工坊；forge-hero = Forge Hero 内嵌；light = 旧版 forge 白底 */
  variant?: "light" | "workshop" | "forge-hero";
  /** document = 由外层容器滚动；panel = 消息区内部滚动 */
  scrollMode?: "panel" | "document";
  /** 对话消息之后、输入框之前的业务内容，例如 HITL、模板与试用提示 */
  conversationFooter?: ReactNode;
};

export function ChatPanel({
  messages,
  input,
  onInputChange,
  onSend,
  disabled,
  sendDisabled,
  streaming,
  placeholder,
  className,
  showComposer = true,
  variant = "light",
  scrollMode = "panel",
  conversationFooter,
}: Props) {
  const t = useT();
  const composerId = useId();
  const workshop = variant === "workshop" || variant === "forge-hero";
  const hero = variant === "forge-hero";
  const documentScroll = hero && scrollMode === "document";
  const composerPlaceholder = placeholder ?? t("describeIteration");
  const lastAssistantId = [...messages]
    .reverse()
    .find((m) => m.role === "assistant")?.id;
  return (
    <section
      className={cn(
        "flex flex-col",
        documentScroll ? "min-h-0" : "h-full min-h-0 overflow-hidden",
        hero
          ? "bg-transparent"
          : cn(
              "rounded-2xl border",
              workshop
                ? "gf-border-subtle gf-glass border bg-[var(--gf-surface)]"
                : "border-black/[0.08] bg-white",
            ),
        className,
      )}
    >
      {!hero ? (
        <header className="gf-border-subtle flex items-center justify-between border-b px-4 py-3">
          <p
            className={cn(
              "text-sm font-medium",
              workshop ? "gf-page-body" : "text-[#20262d]",
            )}
          >
            {t("requirementChat")}
          </p>
        </header>
      ) : null}

      <div
        className={cn(
          "space-y-4 px-4 py-5 md:px-5",
          documentScroll ? "shrink-0" : "min-h-0 flex-1 overflow-y-auto",
        )}
        aria-live="polite"
      >
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              "flex max-w-[94%] items-start gap-2.5 text-sm leading-relaxed",
              m.role === "user" && "ml-auto flex-row-reverse",
              m.role === "assistant" && "mr-auto",
              m.role === "system" && "mx-auto max-w-full justify-center",
            )}
          >
            {m.role !== "system" ? (
              <span
                className={cn(
                  "mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg border",
                  m.role === "assistant"
                    ? "border-[rgba(var(--gf-primary-rgb),0.16)] bg-[rgba(var(--gf-primary-rgb),0.08)] gf-text-accent"
                    : "border-black/[0.07] bg-black/[0.035] gf-page-muted",
                )}
              >
                {m.role === "assistant" ? (
                  <Bot className="h-3.5 w-3.5" aria-hidden="true" />
                ) : (
                  <UserRound className="h-3.5 w-3.5" aria-hidden="true" />
                )}
              </span>
            ) : null}
            <div
              className={cn(
                "min-w-0 break-words",
                m.role === "user" &&
                  (workshop
                    ? "rounded-2xl rounded-tr-md gf-bg-accent-soft px-3.5 py-2.5 gf-page-body gf-ring-accent"
                    : "rounded-2xl rounded-tr-md bg-[#5271ff]/12 px-3.5 py-2.5 text-[#3046a8] ring-1 ring-[#5271ff]/20"),
                m.role === "assistant" &&
                  (workshop
                    ? "rounded-2xl rounded-tl-md bg-black/[0.025] px-3.5 py-2.5 gf-page-body ring-1 ring-[var(--gf-border)]"
                    : "rounded-2xl rounded-tl-md bg-[#eef1f3] px-3.5 py-2.5 text-[#303940] ring-1 ring-black/[0.05]"),
                m.role === "system" &&
                  (workshop
                    ? "rounded-lg bg-amber-50 px-3 py-1.5 text-center font-mono text-[11px] text-amber-900 ring-1 ring-amber-200"
                    : "rounded-lg bg-[#ffcf5a]/15 px-3 py-1.5 text-center font-mono text-[11px] text-[#785d14] ring-1 ring-[#d49d12]/20"),
              )}
            >
              {m.content}
              {streaming && m.id === lastAssistantId ? (
                <span
                  className="ml-1 inline-flex items-center gap-1 align-middle"
                  aria-label={t("loading")}
                >
                  {[0, 1, 2].map((dot) => (
                    <span
                      key={dot}
                      className="inline-block h-1 w-1 animate-pulse rounded-full bg-[var(--gf-primary)] opacity-60 motion-reduce:animate-none"
                      style={{ animationDelay: `${dot * 140}ms` }}
                      aria-hidden="true"
                    />
                  ))}
                </span>
              ) : null}
            </div>
          </div>
        ))}
        {conversationFooter ? (
          <div className="space-y-4 pt-1">{conversationFooter}</div>
        ) : null}
      </div>

      {showComposer ? (
        <div
          className={cn(
            hero
              ? "shrink-0 border-t border-[var(--gf-border)] bg-[var(--gf-surface)] p-3 md:p-4"
              : "gf-border-subtle border-t p-3",
          )}
        >
          <div className={cn(hero && "gf-forge-composer-wrap")}>
            <label htmlFor={composerId} className="sr-only">
              {composerPlaceholder}
            </label>
            <textarea
              id={composerId}
              name="forge-requirement"
              autoComplete="off"
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              rows={hero ? 3 : 3}
              disabled={disabled}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSend();
                }
              }}
              className={cn(
                "w-full resize-none px-3 py-2.5 text-sm outline-none disabled:opacity-50",
                hero
                  ? "gf-page-body placeholder:text-[var(--gf-text-muted)] focus-visible:ring-2 focus-visible:ring-[rgba(var(--gf-primary-rgb),0.3)]"
                  : cn(
                      "rounded-xl border",
                      workshop
                        ? "gf-input"
                        : "border-black/[0.1] bg-[#f5f7f8] text-[#20262d] placeholder:text-[#9099a1] focus-visible:ring-2 focus-visible:ring-[#5271ff]/25",
                    ),
              )}
              placeholder={composerPlaceholder}
            />
            <div
              className={cn(
                "flex items-center justify-between gap-2",
                hero ? "px-2 pb-2" : "mt-2",
              )}
            >
              <span
                className={cn(
                  "font-mono text-[10px]",
                  workshop ? "gf-page-muted" : "text-[#9099a1]",
                )}
              >
                {t("chatSendHint")}
              </span>
              <Button
                variant="primary"
                className={cn(
                  hero
                    ? "gf-forge-send-btn gf-btn-primary gf-interactive !min-h-11 !border-0 !px-4 !py-2.5"
                    : "!min-h-10 !rounded-lg !px-4 !py-2",
                  !hero &&
                    (workshop
                      ? "gf-btn-primary gf-interactive !border-0"
                      : "!bg-[#20262d] !text-white hover:!bg-[#303940]"),
                )}
                disabled={sendDisabled ?? (disabled || !input.trim())}
                onClick={onSend}
              >
                <Send className="h-3.5 w-3.5" />
                {t("sendRequirement")}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
