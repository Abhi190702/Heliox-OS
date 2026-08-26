import { get, writable } from "svelte/store";
import { beforeEach, describe, expect, it, vi } from "vitest";

type NotificationHandler = (method: string, params: unknown) => void;
let notificationHandler: NotificationHandler | null = null;

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return {
    ...actual,
    call: daemonMocks.call,
    connect: vi.fn().mockResolvedValue(true),
    isConnected: vi.fn(() => true),
    onConnectionState: vi.fn(),
    onNotification: (handler: NotificationHandler) => {
      notificationHandler = handler;
    },
  };
});

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

describe("proactive suggestion outcomes", () => {
  beforeEach(() => {
    localStorage.clear();
    notificationHandler = null;
    daemonMocks.call.mockReset();
    vi.resetModules();
  });

  it("keeps a suggestion visible when dismissal is rejected", async () => {
    daemonMocks.call.mockResolvedValue({ status: "error", message: "Suggestion not found: suggestion-1" });
    const { session } = await import("./session");
    notificationHandler!("proactive_suggestion", {
      suggestion_id: "suggestion-1",
      title: "Review the failed task",
      description: "Inspect the latest failure before retrying.",
    });

    await session.dismissProactiveSuggestion();

    const state = get(session);
    expect(state.proactiveSuggestion?.suggestionId).toBe("suggestion-1");
    expect(state.proactiveSuggestionPending).toBe(false);
    expect(state.messages.at(-1)?.text).toContain("Suggestion not found: suggestion-1");
  });

  it("clears a suggestion only after acknowledged dismissal", async () => {
    daemonMocks.call.mockResolvedValue({ status: "ok", dismissed: true, suggestion_id: "suggestion-2" });
    const { session } = await import("./session");
    notificationHandler!("proactive_suggestion", {
      suggestion_id: "suggestion-2",
      title: "Review the failed task",
      description: "Inspect the latest failure before retrying.",
    });

    await session.dismissProactiveSuggestion();

    expect(get(session).proactiveSuggestion).toBeNull();
    expect(daemonMocks.call).toHaveBeenCalledWith("proactive_dismiss", { suggestion_id: "suggestion-2" });
  });
});
