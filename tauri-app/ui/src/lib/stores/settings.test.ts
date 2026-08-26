import { get } from "svelte/store";
import { beforeEach, describe, expect, it, vi } from "vitest";

const daemonMocks = vi.hoisted(() => ({
  call: vi.fn(),
}));

vi.mock("../api/daemon", () => ({
  call: daemonMocks.call,
}));

describe("settings daemon synchronization", () => {
  beforeEach(() => {
    localStorage.clear();
    daemonMocks.call.mockReset();
    vi.resetModules();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({
        matches: false,
        addEventListener: vi.fn(),
      })),
    });
  });

  it("deep-merges daemon settings without erasing local theme and hotkey", async () => {
    localStorage.setItem(
      "heliox_settings",
      JSON.stringify({
        theme: "light",
        hotkey: "Alt+Space",
        model: { provider: "cloud" },
      }),
    );
    daemonMocks.call.mockResolvedValue({
      model: { provider: "ollama", ollama_model: "qwen-test" },
      security: { root_enabled: false },
    });

    const { settings } = await import("./settings");
    await vi.waitFor(() => expect(daemonMocks.call).toHaveBeenCalledWith("get_config"));
    await vi.waitFor(() => expect(get(settings).model.provider).toBe("ollama"));

    expect(get(settings)).toMatchObject({
      theme: "light",
      hotkey: "Alt+Space",
      model: {
        provider: "ollama",
        ollama_model: "qwen-test",
        max_tokens_per_task: 100000,
      },
      security: {
        root_enabled: false,
        dry_run: false,
        snapshot_on_destructive: true,
      },
    });
  });

  it("does not display daemon-backed settings that the daemon rejected", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "get_config") return Promise.resolve({});
      return Promise.reject(new Error("daemon unavailable"));
    });

    const { settings } = await import("./settings");
    await vi.waitFor(() => expect(daemonMocks.call).toHaveBeenCalledWith("get_config"));

    const saved = await settings.updateSection("model", { provider: "cloud" });

    expect(saved).toBe(false);
    expect(get(settings).model.provider).toBe("ollama");
    expect(JSON.parse(localStorage.getItem("heliox_settings") || "{}").model?.provider).toBe("ollama");
  });

  it("keeps purely local appearance settings usable while the daemon is offline", async () => {
    daemonMocks.call.mockRejectedValue(new Error("daemon unavailable"));

    const { settings } = await import("./settings");
    await vi.waitFor(() => expect(daemonMocks.call).toHaveBeenCalledWith("get_config"));
    daemonMocks.call.mockClear();

    const saved = await settings.updateSection("", { theme: "light" });

    expect(saved).toBe(true);
    expect(get(settings).theme).toBe("light");
    expect(daemonMocks.call).not.toHaveBeenCalled();
  });

  it("keeps the displayed settings when the daemon rejects a factory reset", async () => {
    localStorage.setItem("heliox_settings", JSON.stringify({ model: { provider: "cloud" } }));
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "get_config") return Promise.resolve({ model: { provider: "cloud" } });
      return Promise.reject(new Error("daemon unavailable"));
    });

    const { settings } = await import("./settings");
    await vi.waitFor(() => expect(get(settings).model.provider).toBe("cloud"));

    const reset = await settings.reset();

    expect(reset).toBe(false);
    expect(get(settings).model.provider).toBe("cloud");
    expect(JSON.parse(localStorage.getItem("heliox_settings") || "{}").model.provider).toBe("cloud");
  });

  it("clears local state only after the daemon confirms a factory reset", async () => {
    localStorage.setItem("heliox_settings", JSON.stringify({ model: { provider: "cloud" } }));
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "get_config") return Promise.resolve({ model: { provider: "cloud" } });
      if (method === "reset_config") return Promise.resolve({ status: "ok", runtime_reconciled: true });
      return Promise.reject(new Error(`unexpected method: ${method}`));
    });

    const { settings } = await import("./settings");
    await vi.waitFor(() => expect(get(settings).model.provider).toBe("cloud"));

    const reset = await settings.reset();

    expect(reset).toBe(true);
    expect(get(settings).model.provider).toBe("ollama");
    expect(localStorage.getItem("heliox_settings")).toBeNull();
  });
});
