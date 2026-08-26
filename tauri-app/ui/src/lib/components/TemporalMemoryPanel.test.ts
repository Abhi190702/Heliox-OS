import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TemporalMemoryPanel from "./TemporalMemoryPanel.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});

afterEach(cleanup);

describe("temporal memory result handling", () => {
  beforeEach(() => {
    daemonMocks.call.mockReset();
  });

  it("keeps a fact visible and reports why retraction was rejected", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "temporal_memory_status") {
        return Promise.resolve({
          status: "ok",
          available: true,
          counts: { facts: { active: 1 }, episodes: 0, working_items: 0 },
          facts: [
            {
              fact_id: "fact-1",
              subject: "user",
              predicate: "preferred_editor",
              value: "Codex",
              scope: "user",
              status: "active",
              confidence: 0.9,
              provenance: "verified_outcome",
              evidence_count: 3,
              updated_at: "2026-08-26T00:00:00Z",
            },
          ],
        });
      }
      if (method === "temporal_memory_retract") {
        return Promise.resolve({ status: "error", message: "The memory was already retracted elsewhere" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(TemporalMemoryPanel);
    const forget = await screen.findByRole("button", { name: "Forget preferred editor" });
    await fireEvent.click(forget);
    await fireEvent.click(screen.getByRole("button", { name: "Forget preferred editor" }));

    expect((await screen.findByRole("alert")).textContent).toContain("The memory was already retracted elsewhere");
    expect(screen.getByText("Codex")).toBeTruthy();
    expect(daemonMocks.call).toHaveBeenCalledTimes(2);
  });
});
