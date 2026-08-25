import { Bot, Loader2, UserRound } from "lucide-react";
import { ForgeComposer } from "@/components/forge/ForgeComposer";
import { ChatThinking } from "@/components/forge/ChatThinking";
import { MarkdownLite } from "@/components/forge/MarkdownLite";
import {
  groupChatMessages,
  isLongChatMessage,
  type ChatMsg,
} from "@/components/forge/chat-blocks";
import { cn } from "@/lib/cn";
import { useT } from "@/i18n/use-t";
import { useEffect, useRef, useState, type ReactNode } from "react";

export type { ChatMsg, ChatKind } from "@/components/forge/chat-blocks";

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
  /** 对话消息之后、输入框之前的业务内容，例如试用提示 */
  conversationFooter?: ReactNode;
  /** 覆盖底栏输入框（HITL 确认卡等）；有值时不渲染 Composer */
  composerCover?: ReactNode;
  canLoadEarlier?: boolean;
  loadingEarlier?: boolean;
  onLoadEarlier?: () => void;
};

const FOLLOW_THRESHOLD_PX = 48;
const CHAT_ROW_WIDTH = "flex max-w-[min(42rem,85%)] items-start gap-2.5 text-sm leading-relaxed";

function ChatPlainText({
  content,
  collapsible,
}: {
  content: string;
  collapsible: boolean;
}) {
  const t = useT();
  const long = collapsible && isLongChatMessage(content);
  const [expanded, setExpanded] = useState(false);
  return (
    <div>
      <p
        className={cn(
          "whitespace-pre-wrap",
          long && !expanded && "line-clamp-6",
        )}
      >
        {content}
      </p>
      {long ? (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="gf-interactive mt-1.5 cursor-pointer text-xs font-medium gf-text-accent hover:underline"
        >
          {expanded ? t("collapseMessage") : t("expandMessage")}
        </button>
      ) : null}
    </div>
  );
}

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
  composerCover,
  canLoadEarlier,
  loadingEarlier,
  onLoadEarlier,
}: Props) {
  const t = useT();
  const workshop = variant === "workshop" || variant === "forge-hero";
  const hero = variant === "forge-hero";
  const documentScroll = hero && scrollMode === "document";
  const panelScroll = !documentScroll;
  const composerPlaceholder = placeholder ?? t("describeIteration");
  const lastAssistantId = [...messages]
    .reverse()
    .find((m) => m.role === "assistant" && m.kind !== "thinking")?.id;
  const blocks = groupChatMessages(messages);
  const lastBlock = blocks[blocks.length - 1];
  const thinkingLive = Boolean(
    streaming && lastBlock?.type === "thinking",
  );
  const hasUserMessage = messages.some((m) => m.role === "user");

  const scrollRef = useRef<HTMLDivElement>(null);
  const followLatestRef = useRef(true);

  // 用户上翻阅读历史时暂停自动跟底；回到底部附近再恢复
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !panelScroll) return;
    function onScroll() {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      followLatestRef.current = distance < FOLLOW_THRESHOLD_PX;
    }
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [panelScroll]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !panelScroll) return;
    if (!followLatestRef.current && !streaming) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, streaming, conversationFooter, panelScroll]);

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
        ref={panelScroll ? scrollRef : undefined}
        className={cn(
          "space-y-3 px-4 py-4 md:px-5",
          documentScroll ? "shrink-0" : "min-h-0 flex-1 overflow-y-auto",
        )}
        aria-live="polite"
      >
        {canLoadEarlier ? (
          <div className="flex justify-center">
            <button
              type="button"
              disabled={loadingEarlier}
              onClick={onLoadEarlier}
              className="gf-interactive gf-page-muted inline-flex min-h-8 cursor-pointer items-center gap-1.5 rounded-lg px-3 text-xs hover:bg-black/[0.04] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loadingEarlier ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : null}
              {t("forgeLoadEarlier")}
            </button>
          </div>
        ) : null}
        {blocks.map((block) => {
          if (block.type === "thinking") {
            return (
              <ChatThinking
                key={block.id}
                items={block.items}
                live={
                  thinkingLive &&
                  lastBlock?.type === "thinking" &&
                  block.id === lastBlock.id
                }
              />
            );
          }
          const m = block.msg;
          // 仅隐藏本地开场欢迎语；分页窗口里 user 前的真实助手消息要保留
          if (hasUserMessage && m.id === "m0") {
            return null;
          }
          const rich = m.kind === "design" || m.kind === "completed";
          return (
          <div
            key={m.id}
            data-chat-row
            className={cn(
              CHAT_ROW_WIDTH,
              m.role === "user" && "ml-auto flex-row-reverse",
              m.role === "assistant" && "mr-auto",
              m.role === "system" && "mx-auto max-w-full justify-center",
            )}
          >
            {m.role !== "system" ? (
              <span
                className={cn(
                  "mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border",
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
                    ? "rounded-2xl rounded-tr-md bg-[rgba(var(--gf-primary-rgb),0.14)] px-3 py-2 gf-page-body ring-1 ring-[rgba(var(--gf-primary-rgb),0.28)]"
                    : "rounded-2xl rounded-tr-md bg-[rgba(37,99,235,0.16)] px-3 py-2 text-[#1e3a8a] ring-1 ring-[rgba(37,99,235,0.28)]"),
                m.role === "assistant" &&
                  (workshop
                    ? "rounded-2xl rounded-tl-md bg-black/[0.04] px-3 py-2 gf-page-body ring-1 ring-[var(--gf-border)]"
                    : "rounded-2xl rounded-tl-md bg-[#e8edf2] px-3 py-2 text-[#1e293b] ring-1 ring-black/[0.06]"),
                m.role === "system" &&
                  (workshop
                    ? "rounded-lg bg-amber-50 px-2.5 py-1 text-center text-[11px] text-amber-900 ring-1 ring-amber-200"
                    : "rounded-lg bg-[#ffcf5a]/15 px-2.5 py-1 text-center text-[11px] text-[#785d14] ring-1 ring-[#d49d12]/20"),
              )}
            >
              {rich ? (
                <MarkdownLite text={m.content} />
              ) : (
                <ChatPlainText
                  content={m.content}
                  collapsible={m.role === "user"}
                />
              )}
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
          );
        })}
        {conversationFooter ? (
          <div className="space-y-2 pt-0.5">{conversationFooter}</div>
        ) : null}
      </div>

      {composerCover ? (
        <div
          className={cn(
            // 相对聊天面板高度封顶，避免日志带展开后仍按 58vh 抢高把确认卡裁切/盖住
            "min-h-0 max-h-[min(42%,22rem)] shrink-0 overflow-y-auto",
            hero
              ? "border-t border-[var(--gf-border)] bg-[var(--gf-surface)] p-3 md:p-3.5"
              : "gf-border-subtle border-t p-3",
          )}
        >
          {composerCover}
        </div>
      ) : showComposer ? (
        <div
          className={cn(
            hero
              ? "shrink-0 border-t border-[var(--gf-border)] bg-[var(--gf-surface)] p-3 md:p-3.5"
              : "gf-border-subtle border-t p-3",
          )}
        >
          <ForgeComposer
            value={input}
            onChange={onInputChange}
            onSend={onSend}
            disabled={disabled}
            sendDisabled={sendDisabled}
            busy={streaming}
            placeholder={composerPlaceholder}
            density="chat"
          />
        </div>
      ) : null}
    </section>
  );
}
