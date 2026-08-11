import { beforeEach, describe, expect, it, vi } from "vitest";
import { get } from "svelte/store";

let notificationHandler: ((method: string, params: unknown) => void) | null = null;

vi.mock("../api/daemon", () => ({
  onNotification: (handler: typeof notificationHandler) => (notificationHandler = handler),
  offNotification: vi.fn(),
}));

describe("multimodal store", () => {
  beforeEach(async () => {
    const { multimodal } = await import("./multimodal");
    multimodal.reset();
  });

  it("records real daemon fusion notifications", async () => {
    const { multimodal } = await import("./multimodal");
    notificationHandler!("multimodal_intent", {
      command: "open settings",
      voice_component: "open settings",
      gesture_component: "",
      gesture_modifier: "",
      fusion_type: "voice_only",
      confidence: 0.9,
      timestamp: 10,
      metadata: {},
    });
    expect(get(multimodal).lastIntent?.command).toBe("open settings");
    expect(get(multimodal).recentIntents).toHaveLength(1);
  });

  it("ignores unrelated daemon notifications", async () => {
    const { multimodal } = await import("./multimodal");
    notificationHandler!("neural_status", { connected: true });
    expect(get(multimodal).lastIntent).toBeNull();
  });
});
