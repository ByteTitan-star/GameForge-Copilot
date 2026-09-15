import type { HitlWaitPayload } from "@/api/ws-types";

const DEFAULT_COMMANDS: Record<string, readonly string[]> = {
  // ADR-18：plan_confirm / art_confirm 固定确认门已取消，仅为存量暂停 run 保留
  plan_confirm: ["approve_plan", "revise_plan", "cancel_run"],
  art_confirm: ["select_art_a", "select_art_b", "revise_art", "revise_plan", "cancel_run"],
  qa_failed: ["retry_implementation", "revise_plan", "cancel_run"],
  sandbox_failed: ["retry_infra", "retry_implementation", "revise_plan", "cancel_run"],
  agent_question: ["answer_question", "cancel_run"],
};

export function hitlCommands(payload: Pick<HitlWaitPayload, "node" | "allowed_commands">): string[] {
  if (payload.allowed_commands && payload.allowed_commands.length > 0) {
    return payload.allowed_commands;
  }
  return [...(DEFAULT_COMMANDS[payload.node] ?? [])];
}

export function hitlAllows(
  payload: Pick<HitlWaitPayload, "node" | "allowed_commands">,
  command: string,
): boolean {
  return hitlCommands(payload).includes(command);
}

export function isHitlRecoveryNode(node: string): boolean {
  return node === "qa_failed" || node === "sandbox_failed";
}

const DECISION_COMMAND: Record<string, Record<string, string>> = {
  plan_confirm: { approve: "approve_plan", modify: "revise_plan" },
  art_confirm: {
    select_a: "select_art_a",
    select_b: "select_art_b",
    modify: "revise_art",
  },
  qa_failed: { approve: "retry_implementation", modify: "retry_implementation" },
  sandbox_failed: { approve: "retry_infra", modify: "retry_implementation" },
  // ADR-18：回答/跳过 ask_user 工具提问走专用 answer_question 命令
  agent_question: { modify: "answer_question", skip: "answer_question" },
};

export function commandForHitlAction(
  node: string,
  decision: string,
  command?: string | null,
): string | undefined {
  if (command) return command;
  return DECISION_COMMAND[node]?.[decision];
}

export function nextPhaseAfterHitl(
  node: string,
  command?: string | null,
): "plan" | "art" | "code" {
  if (command === "revise_plan") return "plan";
  if (command === "answer_question") return "plan";
  if (node === "agent_question") return "plan";
  if (node === "plan_confirm" || node === "art_confirm") return "art";
  return "code";
}
