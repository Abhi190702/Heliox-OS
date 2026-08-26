import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../i18n";
import GestureWorkflowBindings from "./GestureWorkflowBindings.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});

afterEach(cleanup);

describe("gesture workflow binding availability", () => {
  beforeEach(() => daemonMocks.call.mockReset());

  it("does not present an incomplete daemon response as empty bindings", async () => {
    daemonMocks.call.mockResolvedValue({ enabled: false, bindings: [] });

    render(GestureWorkflowBindings);

    expect((await screen.findByRole("alert")).textContent).toContain("Gesture workflow bindings are unavailable");
    expect(screen.queryByRole("button", { name: /add binding/i })).toBeNull();
  });
});
