import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../i18n";
import SelfHealingPanel from "./SelfHealingPanel.svelte";

const daemonMocks = vi.hoisted(() => ({
  call: vi.fn(),
  onNotification: vi.fn(),
  offNotification: vi.fn(),
}));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, ...daemonMocks };
});

afterEach(cleanup);

describe("self-healing approval results", () => {
  beforeEach(() => {
    daemonMocks.call.mockReset();
    daemonMocks.onNotification.mockReset();
    daemonMocks.offNotification.mockReset();
  });

  it("shows when a stale healing approval is rejected", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "self_healing_status") {
        return Promise.resolve({
          status: "ok",
          enabled: true,
          auto_execute_max_tier: 1,
          watched_metrics: ["memory"],
          monitors: {},
          attempts: [
            {
              attempt_id: "attempt-1",
              metric: "memory",
              goal: "Reduce reversible memory pressure",
              plan_id: "plan-1",
              outcome: "proposed",
              max_tier: 1,
              irreversible: false,
              explanation: "A bounded cleanup is available.",
            },
          ],
        });
      }
      if (method === "confirm") {
        return Promise.resolve({ status: "error", message: "Confirmation already resolved for plan_id: plan-1" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(SelfHealingPanel);
    await fireEvent.click(await screen.findByRole("button", { name: "Approve" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Confirmation already resolved");
    expect(daemonMocks.call).toHaveBeenCalledTimes(2);
  });
});
