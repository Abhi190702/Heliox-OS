export type ExecuteMessageType = "result" | "error" | "system";

export interface ClassifiedExecuteResponse {
  status: string;
  messageType: ExecuteMessageType;
  text: string;
}

/**
 * Convert the daemon's terminal response into one explicit UI state.
 *
 * This is intentionally allow-list based. A new or malformed daemon status
 * must show as an error instead of silently falling through to a green result.
 */
export function classifyExecuteResponse(result: Record<string, unknown>): ClassifiedExecuteResponse {
  const status = String(result.status ?? "");
  const text = String(result.message ?? result.explanation ?? "").trim();

  switch (status) {
    case "success":
      return {
        status,
        messageType: "result",
        text: text || "Task completed successfully.",
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
    case "cancelled":
      return {
        status,
        messageType: "system",
        text: text || "Task cancelled.",
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
