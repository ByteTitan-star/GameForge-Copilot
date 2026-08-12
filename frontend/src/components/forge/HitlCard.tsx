import { useEffect, useMemo, useState } from "react";
import { Check, ShieldCheck, X } from "lucide-react";
import type { HitlWaitPayload } from "@/api/ws-types";
import { Button } from "@/components/ui/button";
import { parseDesignDoc, type ParsedDesignDoc } from "@/lib/hitl-design-doc";
import { useT } from "@/i18n/use-t";

type Props = {
  payload: HitlWaitPayload;
  onApprove: (
    doc: HitlWaitPayload["design_doc"],
    modifyText?: string | null,
  ) => void;
  onReject: () => void;
  busy?: boolean;
};

export function HitlCard({ payload, onApprove, onReject, busy }: Props) {
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

  useEffect(() => {
    setGameplay(parsed.gameplay);
    setControls(parsed.controls);
  }, [parsed.gameplay, parsed.controls]);

  // 当前唯一 HITL 节点是 plan_confirm（策划确认）；sandbox_failed/qa_failed 在新版
  // 流程里是 FAILED 终态，不再走人工确认，因此本卡只呈现「确认/修改策划」编辑面板。
  function buildDoc(): ParsedDesignDoc {
    return { ...parsed, gameplay, controls };
  }

  function handleApprove() {
    const doc = buildDoc();
    const modified =
      gameplay !== parsed.gameplay ||
      controls !== parsed.controls ||
      Boolean(modifyFeedback.trim());
    const modifyText = modified
      ? modifyFeedback.trim() || `gameplay: ${gameplay}\ncontrols: ${controls}`
      : null;
    onApprove(doc as HitlWaitPayload["design_doc"], modifyText);
  }

  return (
    <section
      className="overflow-hidden rounded-2xl border border-amber-200/80 bg-white shadow-sm"
      aria-label={t("manualReview")}
    >
      <div className="h-1 bg-amber-400" aria-hidden="true" />
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-amber-50 text-amber-700 ring-1 ring-amber-200">
              <ShieldCheck className="h-4.5 w-4.5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-amber-700">
                {t("manualReview")}
              </p>
              <h3 className="mt-1 break-words text-base font-semibold text-[#3d3219]">
                {t("confirmDesign")} · {parsed.title || payload.node}
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-[#786532]">
                {t("continueAfterApproval")}
              </p>
            </div>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          <label className="block space-y-1.5">
            <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-[#a17f31]">
              {t("gameplay")}
            </span>
            <textarea
              value={gameplay}
              onChange={(e) => setGameplay(e.target.value)}
              rows={3}
              name="hitl-gameplay"
              autoComplete="off"
              className="w-full resize-none rounded-xl border border-black/[0.1] bg-[#fafafa] px-3 py-2.5 text-sm text-[#3d3219] outline-none transition-[border-color,box-shadow] focus-visible:border-amber-400 focus-visible:ring-2 focus-visible:ring-amber-200"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-[#a17f31]">
              {t("controls")}
            </span>
            <textarea
              value={controls}
              onChange={(e) => setControls(e.target.value)}
              rows={2}
              name="hitl-controls"
              autoComplete="off"
              className="w-full resize-none rounded-xl border border-black/[0.1] bg-[#fafafa] px-3 py-2.5 text-sm text-[#3d3219] outline-none transition-[border-color,box-shadow] focus-visible:border-amber-400 focus-visible:ring-2 focus-visible:ring-amber-200"
            />
          </label>
          {parsed.levels.length > 0 ? (
            <div>
              <p className="font-mono text-[10px] text-[#a17f31] uppercase">
                {t("levels")}
              </p>
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {parsed.levels.map((lv) => (
                  <li
                    key={lv}
                    className="rounded-md bg-amber-50 px-2 py-1 text-[12px] text-[#7f631c] ring-1 ring-amber-200"
                  >
                    {lv}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <label className="block space-y-1.5">
            <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-[#a17f31]">
              {t("hitlModifyFeedback")}
            </span>
            <textarea
              value={modifyFeedback}
              onChange={(e) => setModifyFeedback(e.target.value)}
              rows={2}
              placeholder={t("describeIteration")}
              name="hitl-feedback"
              autoComplete="off"
              className="w-full resize-none rounded-xl border border-black/[0.1] bg-[#fafafa] px-3 py-2.5 text-sm text-[#3d3219] outline-none transition-[border-color,box-shadow] placeholder:text-black/35 focus-visible:border-amber-400 focus-visible:ring-2 focus-visible:ring-amber-200"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-black/[0.06] pt-3">
          <Button
            variant="ghost"
            className="!min-h-10 !rounded-lg !px-3 !py-2 !text-[#6f5a25] hover:!bg-amber-50"
            disabled={busy}
            onClick={onReject}
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            {t("rejectAndStop")}
          </Button>
          <Button
            className="!min-h-10 !rounded-lg !bg-[#e5a817] !px-4 !py-2 !text-white hover:!bg-[#cc9410]"
            disabled={busy}
            onClick={handleApprove}
          >
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            {t("approveAndContinue")}
          </Button>
        </div>
      </div>
    </section>
  );
}
