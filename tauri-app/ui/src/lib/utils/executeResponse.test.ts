import { describe, expect, it } from "vitest";
import { classifyExecuteResponse } from "./executeResponse";

describe("classifyExecuteResponse", () => {
  it("shows only explicit success as a result", () => {
    expect(classifyExecuteResponse({ status: "success", message: "Verified." })).toEqual({
      status: "success",
      messageType: "result",
      text: "Verified.",
    });
  });

  it.each(["partial_failure", "blocked_by_critic", "error"])("shows %s as an error", (status) => {
    expect(classifyExecuteResponse({ status, message: "Not successful." }).messageType).toBe("error");
  });

  it("shows cancellation as a neutral system result", () => {
    expect(classifyExecuteResponse({ status: "cancelled", message: "Denied." }).messageType).toBe("system");
  });

  it("fails closed for unknown or missing statuses", () => {
    expect(classifyExecuteResponse({ status: "future_status" }).messageType).toBe("error");
    expect(classifyExecuteResponse({}).text).toContain("not reported as successful");
  });

  it("prefers the terminal message over the planning explanation", () => {
    expect(
      classifyExecuteResponse({
        status: "partial_failure",
        message: "Execution failed with exit code 125.",
        explanation: "Print a greeting.",
      }).text,
    ).toBe("Execution failed with exit code 125.");
  });
});
