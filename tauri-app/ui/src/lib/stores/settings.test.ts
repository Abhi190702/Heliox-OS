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
});
