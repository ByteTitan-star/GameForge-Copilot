import { useEffect, useMemo, useState } from "react";
import { Check, ChevronRight, MessageSquareText, Palette, ShieldCheck, X } from "lucide-react";
import type { HitlWaitPayload } from "@/api/ws-types";
import { Button } from "@/components/ui/button";
import { parseDesignDoc, type ParsedDesignDoc } from "@/lib/hitl-design-doc";
import { useT } from "@/i18n/use-t";

type Props = {
  payload: HitlWaitPayload;
  onResolve: (
    decision: string,
    modifyText?: string | null,
    doc?: HitlWaitPayload["design_doc"],
  ) => void;
  onReject: () => void;
  busy?: boolean;
};

/** 按内容行数估算 textarea 行高，避免固定 rows=4 留白过多 */
function textareaRows(text: string, min = 2, max = 3): number {
  const lines = text.split("\n").length;
  return Math.min(max, Math.max(min, lines));
}

const fieldClass =
  "w-full resize-none border border-black/[0.1] bg-white px-2.5 py-1.5 text-[12px] leading-5 text-[#20262d] outline-none";

function ReviewHeader({ art, title }: { art: boolean; title: string }) {
  const t = useT();
  return (
    <div className="flex items-center justify-between gap-2 border-b border-black/[0.08] px-3 py-2 sm:px-3.5">
      <div className="flex min-w-0 items-center gap-2">
        <span
          className={`grid h-6 w-6 shrink-0 place-items-center border ${
            art
              ? "border-[#b9d9d4] bg-[#eef8f6] text-[#17665f]"
              : "border-[#e5d5b1] bg-[#fff8e8] text-[#8b641c]"
          }`}
        >
          {art ? (
            <Palette className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
          )}
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
            <span className="font-mono text-[9px] font-medium uppercase tracking-[0.12em] text-black/45">
              {t("manualReview")}
            </span>
            <span className="text-black/20" aria-hidden="true">
              /
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-black/45">
              {art ? "02/03" : "01/03"}
            </span>
          </div>
          <h3 className="truncate text-[13px] font-semibold leading-tight tracking-[-0.01em] text-[#20262d]">
            {title}
          </h3>
        </div>
      </div>
      <span
        className={`shrink-0 border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.08em] ${
          art
            ? "border-[#b9d9d4] bg-[#f3fbf9] text-[#17665f]"
            : "border-[#e5d5b1] bg-[#fffaf0] text-[#8b641c]"
        }`}
      >
        {t("awaitingInput")}
      </span>
    </div>
  );
}

export function HitlCard({ payload, onResolve, onReject, busy }: Props) {
  const t = useT();
  const parsed = useMemo(
    () =>
      parseDesignDoc(
        payload.design_doc,
        typeof payload.design_doc === "object" &&
          payload.design_doc &&
          "title" in payload.design_doc
          ? String((payload.design_doc as { title?: string }).title ?? "")
          : "",
      ),
    [payload.design_doc],
  );
  const [gameplay, setGameplay] = useState(parsed.gameplay);
  const [controls, setControls] = useState(parsed.controls);
  const [modifyFeedback, setModifyFeedback] = useState("");
  const [selectedOption, setSelectedOption] = useState<"A" | "B" | null>(null);
  const isArtReview = payload.node === "art_confirm";

  useEffect(() => {
    setGameplay(parsed.gameplay);
    setControls(parsed.controls);
  }, [parsed.gameplay, parsed.controls]);

  useEffect(() => {
    setModifyFeedback("");
    setSelectedOption(null);
  }, [payload.node, payload.art_options]);

  function buildDoc(): ParsedDesignDoc {
    return { ...parsed, gameplay, controls };
  }

  function handlePlanResolve() {
    const doc = buildDoc();
    const modified =
      gameplay !== parsed.gameplay ||
      controls !== parsed.controls ||
      Boolean(modifyFeedback.trim());
    const modifyText = modified
      ? modifyFeedback.trim() || `gameplay: ${gameplay}\ncontrols: ${controls}`
      : null;
    onResolve(
      modified ? "modify" : "approve",
      modifyText,
      doc as HitlWaitPayload["design_doc"],
    );
  }

  function handleArtResolve() {
    if (selectedOption) {
      onResolve(`select_${selectedOption.toLowerCase()}`);
      return;
    }
    if (modifyFeedback.trim()) onResolve("modify", modifyFeedback.trim());
  }

  const artOptions = payload.art_options?.options ?? [];
  const artActionReady = Boolean(selectedOption || modifyFeedback.trim());

  return (
    <section
      className="overflow-hidden border border-black/[0.1] bg-[#fffdfa] shadow-[0_4px_16px_rgba(38,48,56,0.06)]"
      aria-label={isArtReview ? t("chooseArtDirection") : t("manualReview")}
    >
      <ReviewHeader
        art={isArtReview}
        title={isArtReview ? t("chooseArtDirection") : `${t("confirmDesign")} · ${parsed.title || payload.node}`}
      />

      {isArtReview ? (
        <div className="space-y-2.5 p-3 sm:px-3.5">
          <p className="text-[12px] leading-4 text-black/55">{t("chooseArtDirectionHint")}</p>

          <div className="grid gap-2 sm:grid-cols-2">
            {artOptions.map((option) => {
              const active = selectedOption === option.id;
              return (
                <button
                  key={option.id}
                  type="button"
                  disabled={busy}
                  aria-pressed={active}
                  onClick={() => setSelectedOption(option.id)}
                  className={`group flex min-h-[100px] flex-col border p-2.5 text-left transition-[border-color,background-color,box-shadow] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#23877d]/35 ${
                    active
                      ? "border-[#23877d] bg-[#f2faf8] shadow-[inset_3px_0_0_#23877d]"
                      : "border-black/[0.1] bg-white hover:border-[#8dbdb7] hover:bg-[#fbfefd]"
                  }`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span
                        className={`grid h-5 w-5 shrink-0 place-items-center border font-mono text-[10px] font-semibold ${
                          active
                            ? "border-[#23877d] bg-[#23877d] text-white"
                            : "border-black/15 text-black/55"
                        }`}
                      >
                        {active ? <Check className="h-3 w-3" aria-hidden="true" /> : option.id}
                      </span>
                      <span className="truncate text-[12px] font-semibold text-[#20262d]">{option.name}</span>
                    </span>
                    {option.recommended ? (
                      <span className="shrink-0 font-mono text-[9px] uppercase tracking-[0.06em] text-[#17665f]">
                        {t("recommended")}
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1.5 line-clamp-3 flex-1 text-[11px] leading-4 text-black/58">
                    {option.summary}
                  </span>
                  <span className="mt-1.5 flex items-center gap-0.5 text-[10px] font-medium text-[#17665f] opacity-0 transition-opacity group-hover:opacity-100">
                    {active ? t("selected") : t("selectDirection")}
                    <ChevronRight className="h-3 w-3" aria-hidden="true" />
                  </span>
                </button>
              );
            })}
          </div>

          <label className="block">
            <span className="mb-1 flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.1em] text-black/45">
              <MessageSquareText className="h-3 w-3" aria-hidden="true" />
              {t("artFeedback")}
            </span>
            <textarea
              aria-label={t("artFeedback")}
              value={modifyFeedback}
              onChange={(event) => {
                setModifyFeedback(event.target.value);
                if (event.target.value.trim()) setSelectedOption(null);
              }}
              rows={2}
              name="art-feedback"
              autoComplete="off"
              placeholder={t("artFeedback")}
              className={`${fieldClass} placeholder:text-black/30 focus:border-[#23877d] focus:ring-2 focus:ring-[#23877d]/12`}
            />
          </label>
        </div>
      ) : (
        <div className="space-y-2 p-3 sm:px-3.5">
          <p className="text-[11px] leading-4 text-black/50">{t("continueAfterApproval")}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block font-mono text-[9px] uppercase tracking-[0.1em] text-black/45">
                {t("gameplay")}
              </span>
              <textarea
                value={gameplay}
                onChange={(event) => setGameplay(event.target.value)}
                rows={textareaRows(gameplay)}
                name="hitl-gameplay"
                autoComplete="off"
                className={`${fieldClass} focus:border-[#d09a2d] focus:ring-2 focus:ring-[#d09a2d]/12`}
              />
            </label>
            <label className="block">
              <span className="mb-1 block font-mono text-[9px] uppercase tracking-[0.1em] text-black/45">
                {t("controls")}
              </span>
              <textarea
                value={controls}
                onChange={(event) => setControls(event.target.value)}
                rows={textareaRows(controls)}
                name="hitl-controls"
                autoComplete="off"
                className={`${fieldClass} focus:border-[#d09a2d] focus:ring-2 focus:ring-[#d09a2d]/12`}
              />
            </label>
          </div>
          {parsed.levels.length > 0 ? (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-black/[0.06] pt-2">
              <span className="shrink-0 font-mono text-[9px] uppercase tracking-[0.1em] text-black/45">
                {t("levels")}
              </span>
              <div className="flex min-w-0 flex-1 flex-wrap gap-1">
                {parsed.levels.map((level) => (
                  <span
                    key={level}
                    className="border border-black/[0.09] bg-white px-1.5 py-0.5 text-[10px] text-black/60"
                  >
                    {level}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          <label className="block">
            <span className="mb-1 flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.1em] text-black/45">
              <MessageSquareText className="h-3 w-3" aria-hidden="true" />
              {t("hitlModifyFeedback")}
            </span>
            <textarea
              aria-label={t("hitlModifyFeedback")}
              value={modifyFeedback}
              onChange={(event) => setModifyFeedback(event.target.value)}
              rows={2}
              placeholder={t("describeIteration")}
              name="hitl-feedback"
              autoComplete="off"
              className={`${fieldClass} focus:border-[#d09a2d] focus:ring-2 focus:ring-[#d09a2d]/12`}
            />
          </label>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-1.5 border-t border-black/[0.08] bg-[#faf8f3] px-3 py-2 sm:px-3.5">
        <Button
          variant="ghost"
          className="!min-h-8 !rounded-md !px-2 !text-[11px] !text-black/50 hover:!bg-black/[0.04] hover:!text-black/75"
          disabled={busy}
          onClick={onReject}
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
          {t("rejectAndStop")}
        </Button>
        <Button
          className={`!min-h-8 !rounded-md !px-3 !text-[11px] !font-semibold !text-white ${
            isArtReview
              ? "!bg-[#17665f] hover:!bg-[#12534e]"
              : "!bg-[#a87516] hover:!bg-[#8d6212]"
          }`}
          disabled={busy || (isArtReview ? !artActionReady : false)}
          onClick={isArtReview ? handleArtResolve : handlePlanResolve}
        >
          {isArtReview
            ? selectedOption
              ? `${t("selectDirection")} · ${selectedOption}`
              : t("regenerateArtOptions")
            : t("approveAndContinue")}
          <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      </div>
    </section>
  );
}
