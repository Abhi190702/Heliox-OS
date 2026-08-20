import { get, writable } from "svelte/store";
import { beforeEach, describe, expect, it, vi } from "vitest";

type NotificationHandler = (method: string, params: unknown) => void;
let notificationHandler: NotificationHandler | null = null;

const daemonMocks = vi.hoisted(() => ({
  call: vi.fn(),
}));

vi.mock("../api/daemon", () => ({
  call: daemonMocks.call,
  connect: vi.fn().mockResolvedValue(true),
  isConnected: vi.fn(() => true),
  onConnectionState: vi.fn(),
  onNotification: (handler: NotificationHandler) => {
    notificationHandler = handler;
  },
}));

vi.mock("./settings", () => ({
  settings: writable({ model: { cloud_model: "ollama" } }),
}));

vi.mock("./companion", () => ({
  companion: { speak: vi.fn() },
}));

vi.mock("@tauri-apps/plugin-notification", () => ({
  isPermissionGranted: vi.fn().mockResolvedValue(false),
  requestPermission: vi.fn().mockResolvedValue("denied"),
  sendNotification: vi.fn(),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function requireConfirmation(planId: string) {
  notificationHandler!("confirm_required", {
    plan_id: planId,
    actions: [{ index: 0, action_type: "browser_navigate", target: "https://example.test" }],
  });
}

describe("confirmation acknowledgement", () => {
  beforeEach(() => {
    localStorage.clear();
    notificationHandler = null;
    daemonMocks.call.mockReset();
    vi.resetModules();
  });

  it("keeps the dialog pending until the daemon acknowledges the decision", async () => {
    const acknowledgement = deferred<Record<string, unknown>>();
    daemonMocks.call.mockReturnValueOnce(acknowledgement.promise);
    const { session } = await import("./session");
    requireConfirmation("plan-approve");

    const decision = session.confirm(true, [0]);
    expect(get(session)).toMatchObject({
      confirmRequired: true,
      confirmPlanId: "plan-approve",
      confirmSubmitting: true,
    });

    acknowledgement.resolve({ status: "ok", confirmed: true });
    await decision;

    expect(daemonMocks.call).toHaveBeenCalledWith("confirm", {
      plan_id: "plan-approve",
      confirmed: true,
      approved_indices: [0],
    });
    expect(get(session)).toMatchObject({ confirmRequired: false, confirmSubmitting: false });
  });

  it("ignores duplicate submissions and does not let a stale acknowledgement dismiss a newer plan", async () => {
    const acknowledgement = deferred<Record<string, unknown>>();
    daemonMocks.call.mockReturnValueOnce(acknowledgement.promise);
    const { session } = await import("./session");
    requireConfirmation("plan-old");

    const oldDecision = session.confirm(true, [0]);
    await session.confirm(false);
    expect(daemonMocks.call).toHaveBeenCalledTimes(1);

    requireConfirmation("plan-new");
    acknowledgement.resolve({ status: "ok", confirmed: true });
    await oldDecision;

    expect(get(session)).toMatchObject({
      confirmRequired: true,
      confirmPlanId: "plan-new",
      confirmSubmitting: false,
    });
  });
});
