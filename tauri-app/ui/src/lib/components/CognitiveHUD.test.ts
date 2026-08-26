import { cleanup, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CognitiveHUD from "./CognitiveHUD.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call, isConnected: () => true };
});

afterEach(cleanup);

describe("CognitiveHUD response contract", () => {
  beforeEach(() => daemonMocks.call.mockReset());

  it("does not mark an incomplete cognitive response as connected", async () => {
    daemonMocks.call.mockResolvedValue({ attention_score: 1, stress_level: 0, cognitive_load: 0 });

    const { container } = render(CognitiveHUD);

    await waitFor(() => expect(daemonMocks.call).toHaveBeenCalled());
    expect(container.querySelector(".cognitive-hud")?.classList.contains("active")).toBe(false);
  });

  it("activates only for an acknowledged numeric cognitive sample", async () => {
    daemonMocks.call.mockResolvedValue({
      status: "ok",
      attention_score: 0.8,
      stress_level: 0.1,
      cognitive_load: 0.2,
      confidence: 0.7,
      signal_sources: 2,
      dominant_modality: "behavioral",
    });

    const { container } = render(CognitiveHUD);

    await waitFor(() => expect(container.querySelector(".cognitive-hud")?.classList.contains("active")).toBe(true));
  });
});
