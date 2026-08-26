import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "./invoke";

describe("browser invoke bridge", () => {
  beforeEach(() => {
    delete (window as any).__TAURI_INTERNALS__;
    vi.restoreAllMocks();
  });

  it("returns only a successful proxy response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ cpu: 27 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(invoke("get_system_stats")).resolves.toEqual({ cpu: 27 });
  });

  it("surfaces an unsupported command instead of returning fabricated data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "Command is unavailable in browser development." }), {
          status: 501,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(invoke("get_temperature_stats")).rejects.toThrow("Command is unavailable in browser development.");
  });

  it("surfaces a failed proxy connection instead of returning an empty success object", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));

    await expect(invoke("unknown_command")).rejects.toThrow("connection refused");
  });
});
