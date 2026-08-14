export type ExecuteMessageType = "result" | "error" | "system";

export interface ClassifiedExecuteResponse {
  status: string;
  messageType: ExecuteMessageType;
  text: string;
}

export interface NormalizableActionResult {
  action_type: string;
  target: string;
  success: boolean;
  output: string;
  error: string | null;
}

export interface NormalizableMessage {
  type: string;
  text: string;
  plan?: { explanation?: string };
}

const CODE_EXECUTION_FAILURE_OUTPUT = /^\s*(?:An unexpected error occurred:|Traceback \(most recent call last\):)/i;

/**
 * Repair action results written by older daemons that swallowed Python
 * exceptions into stdout and incorrectly persisted them as successful.
 */
export function normalizeActionResult<T extends NormalizableActionResult>(result: T): T {
  if (result.success && result.action_type === "code_execute" && CODE_EXECUTION_FAILURE_OUTPUT.test(result.output)) {
    return {
      ...result,
      success: false,
      output: "",
      error: result.error || result.output.trim(),
    };
  }
  return result;
}

/**
 * Convert the daemon's terminal response into one explicit UI state.
 *
 * This is intentionally allow-list based. A new or malformed daemon status
 * must show as an error instead of silently falling through to a green result.
 */
export function classifyExecuteResponse(result: Record<string, unknown>): ClassifiedExecuteResponse {
  const status = String(result.status ?? "");
  const message = String(result.message ?? "").trim();
  const legacySuccessExplanation = status === "success" ? String(result.explanation ?? "").trim() : "";
  const text = message || legacySuccessExplanation;
  const rawFollowUp = result.companion_follow_up;
  const followUp =
    rawFollowUp && typeof rawFollowUp === "object"
      ? (rawFollowUp as { message?: unknown; suggestions?: unknown })
      : null;
  const followUpMessage = String(followUp?.message ?? "").trim();
  const followUpSuggestions = Array.isArray(followUp?.suggestions)
    ? followUp.suggestions
        .map((item) => String(item).trim())
        .filter(Boolean)
        .slice(0, 3)
    : [];
  const companionText =
    followUpMessage && followUpSuggestions.length > 0
      ? `${followUpMessage}\n\nPossible next steps:\n${followUpSuggestions.map((idea) => `- ${idea}`).join("\n")}`
      : "";
  const successText = [text || "Task completed successfully.", companionText].filter(Boolean).join("\n\n");

  switch (status) {
    case "success":
      return {
        status,
        messageType: "result",
        text: successText,
      };
    case "partial_failure":
      return {
        status,
        messageType: "error",
        text: text || "Task completed with errors.",
      };
    case "blocked_by_critic":
      return {
        status,
        messageType: "error",
        text: text || "The safety review blocked this plan before execution.",
      };
    case "blocked_by_companion":
      return {
        status,
        messageType: "error",
        text: text || "The interactive companion stopped a misaligned plan before execution.",
      };
    case "cancelled":
      return {
        status,
        messageType: "system",
        text: text || "Task cancelled.",
      };
    case "interrupted":
      return {
        status,
        messageType: "system",
        text:
          text ||
          "Task was interrupted before a verified result was returned. No unfinished action was reported as complete.",
      };
    case "revising":
      return {
        status,
        messageType: "system",
        text: text || "The active task accepted your correction and is replanning.",
      };
    case "error":
      return {
        status,
        messageType: "error",
        text: text || "The task failed.",
      };
    default:
      return {
        status: status || "unknown",
        messageType: "error",
        text: `Unexpected daemon response${status ? ` status: ${status}` : ""}. The task was not reported as successful.`,
      };
  }
}

/**
 * Repair terminal cards persisted by older clients that displayed the plan
 * intent as an execution error when the daemon returned no terminal message.
 */
export function repairLegacyPlanFallback<T extends NormalizableMessage>(
  message: T,
  previousPlanExplanation: string,
): T {
  const text = message.text.trim();
  const explanation = previousPlanExplanation.trim();
  if (message.type === "error" && /^Unexpected daemon response status: revising\b/.test(text)) {
    return {
      ...message,
      type: "system",
      text: "The active task accepted your correction and started replanning.",
    };
  }
  if (message.type !== "error" || !text || !explanation || text !== explanation) return message;

  return {
    ...message,
    type: "system",
    text: "Task was interrupted before a verified result was returned. No unfinished action was reported as complete.",
  };
}
