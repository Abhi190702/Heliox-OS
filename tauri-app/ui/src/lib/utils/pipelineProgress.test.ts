import { describe, expect, it } from "vitest";
import { calculatePipelineProgress } from "./pipelineProgress";

describe("calculatePipelineProgress", () => {
  it("finishes cancelled and failed pipelines when every stage is terminal", () => {
    expect(
      calculatePipelineProgress([
        "success",
        "success",
        "success",
        "success",
        "error",
        "error",
        "skipped",
        "skipped",
        "success",
      ]),
    ).toBe(100);
  });

  it("does not finish while a stage is still active or idle", () => {
    expect(calculatePipelineProgress(["success", "error", "active", "idle"])).toBe(50);
  });
});
