import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../i18n";
import NarrationPanel from "./NarrationPanel.svelte";
import SupervisionPanel from "./SupervisionPanel.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});

afterEach(cleanup);

describe("companion settings result handling", () => {
  beforeEach(() => {
    daemonMocks.call.mockReset();
  });

  it("does not claim narration settings were saved after daemon rejection", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "narration_status") {
        return Promise.resolve({
          status: "ok",
          enabled: false,
          narrate_steps: true,
          interrupt_on_risk: true,
          proactive_review_enabled: true,
          live_corrections_enabled: true,
          follow_up_enabled: true,
          confirm_timeout_seconds: 120,
          advisory_timeout_seconds: 5,
        });
      }
      if (method === "proactive_learning_status") return Promise.resolve({ status: "ok", patterns: {} });
      if (method === "narration_config_update") {
        return Promise.resolve({ status: "error", message: "Narration runtime rejected the setting" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(NarrationPanel);
    await fireEvent.click(await screen.findByRole("button", { name: /save/i }));

    expect((await screen.findByRole("alert")).textContent).toContain("Narration runtime rejected the setting");
    expect(screen.queryByText("✓ Saved")).toBeNull();
  });

  it("confirms and validates narration learning resets", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "narration_status") {
        return Promise.resolve({
          status: "ok",
          enabled: false,
          narrate_steps: true,
          interrupt_on_risk: true,
          proactive_review_enabled: true,
          live_corrections_enabled: true,
          follow_up_enabled: true,
          confirm_timeout_seconds: 120,
          advisory_timeout_seconds: 5,
        });
      }
      if (method === "proactive_learning_status") {
        return Promise.resolve({ status: "ok", patterns: { terminal_error: { shown: 2, accepted: 1, dismissed: 1 } } });
      }
      if (method === "online_learning_reset") {
        return Promise.resolve({ status: "error", message: "Learning reset was rejected" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(NarrationPanel);
    await fireEvent.click(await screen.findByRole("button", { name: /reset learning/i }));
    expect(screen.getByRole("button", { name: "Confirm reset learning" })).toBeTruthy();
    expect(daemonMocks.call).toHaveBeenCalledTimes(2);

    await fireEvent.click(screen.getByRole("button", { name: "Confirm reset learning" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Learning reset was rejected");
    expect(daemonMocks.call).toHaveBeenCalledTimes(3);
  });

  it("does not claim supervision settings were saved after daemon rejection", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "supervision_status") {
        return Promise.resolve({
          status: "ok",
          enabled: false,
          keyboard_mouse_hook_enabled: false,
          cognitive_coaching_enabled: true,
          risk_pattern_detection_enabled: true,
          hook_healthy: false,
        });
      }
      if (method === "supervision_config_update") {
        return Promise.resolve({ status: "error", message: "Input hook could not start" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(SupervisionPanel);
    await fireEvent.click(await screen.findByRole("button", { name: /save/i }));

    expect((await screen.findByRole("alert")).textContent).toContain("Input hook could not start");
    expect(screen.queryByText("✓ Saved")).toBeNull();
  });

  it("disables narration controls when status was not acknowledged", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "narration_status") return Promise.resolve({ enabled: true });
      if (method === "proactive_learning_status") return Promise.resolve({ status: "ok", patterns: {} });
      throw new Error(`unexpected method: ${method}`);
    });

    render(NarrationPanel);

    expect((await screen.findByRole("alert")).textContent).toContain("Narration status is unavailable");
    expect((screen.getByRole("button", { name: /save/i }) as HTMLButtonElement).disabled).toBe(true);
  });
});
