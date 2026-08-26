import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { writable } from "svelte/store";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AmbientHUD from "./AmbientHUD.svelte";

const mocks = vi.hoisted(() => ({ call: vi.fn(), invoke: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: mocks.call, isConnected: () => true };
});
vi.mock("../api/invoke", () => ({ invoke: mocks.invoke }));
vi.mock("../stores/session", () => ({
  session: Object.assign(writable({ budget: null, totalTokens: 0, estimatedCost: 0 }), {
    acknowledgeBudgetEvent: vi.fn(),
  }),
}));
vi.mock("../stores/settings", () => ({
  settings: writable({
    model: {
      budget_monthly_limit_usd: 0,
      max_tokens_per_task: 0,
      max_usd_per_task: 0,
      max_tokens_per_action: 0,
      max_consecutive_failures: 0,
      budget_enabled: false,
    },
  }),
}));

afterEach(cleanup);

describe("AmbientHUD telemetry contract", () => {
  beforeEach(() => {
    mocks.call.mockReset();
    mocks.invoke.mockReset();
    mocks.invoke.mockRejectedValue(new Error("native fallback unavailable"));
  });

  it("does not render incomplete daemon telemetry as zero usage", async () => {
    mocks.call.mockImplementation((method: string) =>
      Promise.resolve(method === "system_info" ? { status: "ok" } : "1h 0m"),
    );
    render(AmbientHUD);
    await fireEvent.click(screen.getByRole("button", { name: "Toggle HUD" }));

    await waitFor(() => expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0));
  });

  it("renders an acknowledged complete telemetry sample", async () => {
    mocks.call.mockImplementation((method: string) =>
      Promise.resolve(
        method === "system_info"
          ? {
              status: "ok",
              cpu_percent: 42,
              memory_percent: 50,
              memory_used: 4 * 1024 ** 3,
              memory_total: 8 * 1024 ** 3,
              disk_percent: 25,
              disk_used: 100 * 1024 ** 3,
              disk_total: 400 * 1024 ** 3,
              hostname: "test-host",
              uptime_seconds: 3600,
            }
          : "1h 0m",
      ),
    );
    render(AmbientHUD);
    await fireEvent.click(screen.getByRole("button", { name: "Toggle HUD" }));

    await screen.findByText("42%");
    expect(screen.getByText("4.0 / 8.0 GB")).toBeTruthy();
    expect(screen.getByText("TEST-HOST")).toBeTruthy();
  });
});
