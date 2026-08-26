import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CHAT_SESSIONS_KEY } from "../utils/chatSessions";
import ActivityLog from "./ActivityLog.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});
vi.mock("../api/invoke", () => ({ invoke: vi.fn() }));

afterEach(cleanup);

describe("ActivityLog local evidence", () => {
  beforeEach(() => {
    daemonMocks.call.mockReset();
    localStorage.clear();
  });

  it("labels a chat-only fallback as local instead of successful execution", async () => {
    localStorage.setItem(
      CHAT_SESSIONS_KEY,
      JSON.stringify([
        {
          id: "chat-1",
          title: "Greeting",
          createdAt: 10,
          updatedAt: 10,
          messages: [{ type: "user", text: "Hello Heliox", timestamp: 10 }],
          totalTokens: 0,
          estimatedCost: 0,
        },
      ]),
    );
    daemonMocks.call.mockResolvedValue({ status: "ok", entries: [] });

    render(ActivityLog);

    expect(await screen.findByText("Hello Heliox")).toBeTruthy();
    expect(screen.getByText("LOCAL")).toBeTruthy();
    expect(screen.queryByText("OK")).toBeNull();
    expect(screen.getByText(/execution outcome is unavailable/i)).toBeTruthy();
  });
});
