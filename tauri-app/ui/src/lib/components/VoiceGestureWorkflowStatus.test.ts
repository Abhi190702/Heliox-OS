import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../i18n";
import VoiceGestureWorkflowStatus from "./VoiceGestureWorkflowStatus.svelte";

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

describe("voice/gesture workflow controls", () => {
  beforeEach(() => {
    daemonMocks.call.mockReset();
    daemonMocks.onNotification.mockReset();
    daemonMocks.offNotification.mockReset();
  });

  it("surfaces a daemon rejection instead of silently reloading", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "voice_gesture_workflow_list") {
        return Promise.resolve({
          status: "ok",
          workflows: [
            {
              workflow_id: "workflow-1",
              goal: "Review the report",
              invocation_source: "voice",
              steps: [],
              current_step: 0,
              state: "running",
              updated_at: "2026-08-26T00:00:00Z",
            },
          ],
        });
      }
      if (method === "voice_gesture_workflow_pause") {
        return Promise.resolve({ status: "error", message: "Workflow already completed" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(VoiceGestureWorkflowStatus);
    await fireEvent.click(await screen.findByRole("button", { name: "Pause" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Workflow already completed");
    expect(daemonMocks.call).toHaveBeenCalledTimes(2);
  });

  it("reports an unavailable workflow engine instead of an empty archive", async () => {
    daemonMocks.call.mockResolvedValue({
      status: "error",
      message: "Voice/gesture workflow engine not initialized",
      workflows: [],
    });

    render(VoiceGestureWorkflowStatus);

    expect((await screen.findByRole("alert")).textContent).toContain("Voice/gesture workflow engine not initialized");
  });
});
