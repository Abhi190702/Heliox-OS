import { get } from "svelte/store";
import { beforeEach, describe, expect, it, vi } from "vitest";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn(), onNotification: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, ...daemonMocks };
});

describe("Air Handoff daemon contracts", () => {
  beforeEach(() => {
    localStorage.clear();
    daemonMocks.call.mockReset();
    daemonMocks.onNotification.mockReset();
    vi.resetModules();
  });

  it("rejects a receiver state without an explicit acknowledgement", async () => {
    daemonMocks.call.mockResolvedValue({ enabled: true, running: true, paired_devices: [], recent: [] });
    const { airHandoff } = await import("./airHandoff");

    await airHandoff.refresh();

    expect(get(airHandoff)).toMatchObject({ running: false, gestureArmed: false });
    expect(get(airHandoff).error).toContain("Air Handoff status is unavailable");
  });

  it("rejects an incomplete pairing response even when its status is ok", async () => {
    daemonMocks.call.mockResolvedValue({ status: "ok" });
    const { airHandoff } = await import("./airHandoff");

    await expect(airHandoff.startPairing()).rejects.toThrow("pairing response is incomplete");
    expect(get(airHandoff).pairing).toBeNull();
  });

  it("requires the receiver to reach the requested enabled state", async () => {
    daemonMocks.call.mockResolvedValue({ status: "ok", enabled: false, running: false });
    const { airHandoff } = await import("./airHandoff");

    await expect(airHandoff.setEnabled(true)).rejects.toThrow("did not reach the requested state");
    expect(get(airHandoff).enabled).toBe(false);
  });
});
