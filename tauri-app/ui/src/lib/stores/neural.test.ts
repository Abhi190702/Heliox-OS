import { beforeEach, describe, expect, it, vi } from "vitest";
import { get } from "svelte/store";

let notificationHandler: ((method: string, params: unknown) => void) | null = null;
const call = vi.fn();
const invoke = vi.fn();

vi.mock("../api/daemon", () => ({
  call,
  onNotification: (handler: typeof notificationHandler) => (notificationHandler = handler),
  offNotification: vi.fn(),
  requireResultStatus: (
    result: { status?: string; message?: string; error?: string },
    expectedStatus: string | readonly string[],
    fallbackMessage: string,
  ) => {
    const expected = typeof expectedStatus === "string" ? [expectedStatus] : expectedStatus;
    if (!expected.includes(result.status ?? "")) {
      throw new Error(result.message || result.error || fallbackMessage);
    }
    return result;
  },
}));
vi.mock("../api/invoke", () => ({ invoke }));

describe("neural control store", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    call.mockReset();
    invoke.mockReset();
  });

  it("auto-commits a safe preview only after its cancellation window", async () => {
    const { neural } = await import("./neural");
    call.mockImplementation(async (method: string) =>
      method === "neural_commit"
        ? { status: "committed", state: "cooldown", connected: true }
        : { status: "ok", state: "cooldown", connected: true },
    );
    notificationHandler!("neural_preview", {
      status: "previewed",
      preview_id: "preview-1",
      intent_id: "intent-1",
      intent_class: "focus_right",
      command_id: null,
      resolved_command_id: null,
      canonical_goal: "neural_ui.focus_right",
      requested_scope: "navigate",
      state_revision: 4,
      created_at_ns: 1_000_000_000,
      eligible_at_ns: 1_800_000_000,
      expires_at_ns: 3_000_000_000,
      requires_non_neural_approval: false,
      world_model: null,
    });

    await vi.advanceTimersByTimeAsync(799);
    expect(call).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(call).toHaveBeenCalledWith("neural_commit", {
      preview_id: "preview-1",
      expected_revision: 4,
      world_model_approved: false,
    });
    expect(get(neural).preview).toBeNull();
  });

  it("never auto-approves a world-model warning", async () => {
    const { neural } = await import("./neural");
    notificationHandler!("neural_preview", {
      status: "previewed",
      preview_id: "preview-2",
      created_at_ns: 1,
      eligible_at_ns: 2,
      requires_non_neural_approval: true,
    });
    await vi.runAllTimersAsync();
    expect(call).not.toHaveBeenCalledWith("neural_commit", expect.anything());
    expect(get(neural).preview?.preview_id).toBe("preview-2");
  });

  it("cancels auto-commit when a higher-priority safety decision appears", async () => {
    const { neural } = await import("./neural");
    call.mockResolvedValue({ status: "ok", state: "observe_only", connected: true, armed_scope: "observe" });
    notificationHandler!("neural_preview", {
      status: "previewed",
      preview_id: "preview-safety",
      created_at_ns: 1_000_000_000,
      eligible_at_ns: 2_000_000_000,
      requires_non_neural_approval: false,
    });

    const deferred = neural.deferPreviewForSafetyDecision();
    expect(get(neural).preview).toBeNull();
    await vi.runAllTimersAsync();
    await deferred;

    expect(call).toHaveBeenCalledWith("neural_disarm", { reason: "higher_priority_safety_decision" });
    expect(call).not.toHaveBeenCalledWith("neural_commit", expect.anything());
    expect(get(neural).error).toContain("another Heliox safety decision");
  });

  it("emergency disarm clears a pending preview", async () => {
    const { neural } = await import("./neural");
    call.mockResolvedValue({ status: "ok", state: "observe_only", connected: true, armed_scope: "observe" });
    await neural.disarm();
    expect(call).toHaveBeenCalledWith("neural_disarm", { reason: "user_emergency_disarm" });
    expect(get(neural).preview).toBeNull();
  });

  it("keeps the flicker stimulus off until explicit local consent", async () => {
    const { neural } = await import("./neural");
    neural.setStimulusEnabled(false);
    expect(get(neural).stimulusEnabled).toBe(false);
    neural.setStimulusEnabled(true);
    expect(get(neural).stimulusEnabled).toBe(true);
  });

  it("preserves explicit recorded-versus-live evidence provenance", async () => {
    const { neural } = await import("./neural");
    call.mockResolvedValue({
      status: "ok",
      state: "observe_only",
      connected: true,
      source_id: "playback-session",
      board_kind: "local-npz-playback",
      transport: "playback",
      evidence_kind: "recorded_eeg",
    });
    invoke.mockResolvedValue({ running: false, pid: null });
    await neural.refresh();
    expect(get(neural).evidenceKind).toBe("recorded_eeg");
    expect(get(neural).boardKind).toBe("local-npz-playback");
  });

  it("stages an explicit goal instead of accepting free-form neural text", async () => {
    const { neural } = await import("./neural");
    call.mockResolvedValue({
      status: "ok",
      staged_tasks: [
        {
          task_id: "task-1",
          command_id: "staged-task:task-1",
          label: "Research",
          goal: "Research and save a verified summary",
          session_id: "chat-4",
          created_at_ns: 10,
          authority: "explicit_non_neural_staging",
        },
      ],
      focused_command_id: "staged-task:task-1",
    });

    expect(await neural.stageTask("Research", "Research and save a verified summary", "chat-4")).toBe(true);
    expect(call).toHaveBeenCalledWith("neural_stage_task", {
      label: "Research",
      goal: "Research and save a verified summary",
      session_id: "chat-4",
    });
    expect(get(neural).stagedTasks[0]?.authority).toBe("explicit_non_neural_staging");
    expect(get(neural).focusedCommandId).toBe("staged-task:task-1");
  });

  it("keeps a rejected neural preview visible with the daemon error", async () => {
    const { neural } = await import("./neural");
    notificationHandler!("neural_preview", {
      status: "previewed",
      preview_id: "preview-rejected",
      state_revision: 7,
      created_at_ns: 1,
      eligible_at_ns: 2,
      requires_non_neural_approval: true,
    });
    call.mockResolvedValue({ status: "rejected", error: "world-model approval is stale" });

    await neural.approvePreview();

    expect(get(neural).preview?.preview_id).toBe("preview-rejected");
    expect(get(neural).error).toBe("world-model approval is stale");
  });

  it("keeps a verified execution failure visible after refreshing neural status", async () => {
    const { neural } = await import("./neural");
    notificationHandler!("neural_preview", {
      status: "previewed",
      preview_id: "preview-failed",
      state_revision: 8,
      created_at_ns: 1,
      eligible_at_ns: 2,
      requires_non_neural_approval: true,
    });
    call.mockImplementation(async (method: string) =>
      method === "neural_commit"
        ? { status: "failed", error: "desktop action did not verify" }
        : { status: "ok", state: "observe_only", connected: true },
    );
    invoke.mockResolvedValue({ running: false, pid: null });

    await neural.approvePreview();

    expect(get(neural).preview).toBeNull();
    expect(get(neural).lastResult?.status).toBe("failed");
    expect(get(neural).error).toBe("desktop action did not verify");
  });

  it("surfaces an unavailable neural controller instead of reporting a healthy refresh", async () => {
    const { neural } = await import("./neural");
    call.mockResolvedValue({ status: "unavailable", connected: false });
    invoke.mockResolvedValue({ running: false, pid: null });

    await neural.refresh();

    expect(get(neural).connected).toBe(false);
    expect(get(neural).error).toBe("Neural controller is unavailable in the Heliox daemon.");
  });

  it("does not apply a rejected arm response as neural state", async () => {
    const { neural } = await import("./neural");
    notificationHandler!("neural_status", {
      state: "observe_only",
      connected: true,
      session_id: "session-1",
      armed_scope: "observe",
    });
    call.mockResolvedValue({ status: "rejected", error: "calibration is required" });

    await neural.arm("safe_desktop");

    expect(get(neural).state).toBe("observe_only");
    expect(get(neural).armedScope).toBe("observe");
    expect(get(neural).error).toBe("calibration is required");
  });

  it("returns false when the daemon does not acknowledge task staging", async () => {
    const { neural } = await import("./neural");
    call.mockResolvedValue({ status: "unavailable" });

    expect(await neural.stageTask("Research", "Investigate the issue")).toBe(false);
    expect(get(neural).error).toBe("The daemon did not stage the neural task.");
  });
});
