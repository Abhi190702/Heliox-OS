import { beforeEach, describe, expect, it, vi } from "vitest";
import { get } from "svelte/store";

let notificationHandler: ((method: string, params: unknown) => void) | null = null;
const call = vi.fn();
const invoke = vi.fn();

vi.mock("../api/daemon", () => ({
  call,
  onNotification: (handler: typeof notificationHandler) => (notificationHandler = handler),
  offNotification: vi.fn(),
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
    call.mockResolvedValue({ state: "cooldown", connected: true });
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
    call.mockResolvedValue({ state: "observe_only", connected: true, armed_scope: "observe" });
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
    call.mockResolvedValue({ state: "observe_only", connected: true, armed_scope: "observe" });
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
});
