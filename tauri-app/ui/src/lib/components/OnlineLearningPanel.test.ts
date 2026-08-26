import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import OnlineLearningPanel from "./OnlineLearningPanel.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});

const status = {
  status: "ok",
  enabled: true,
  model_version: "1",
  backend: "river",
  authority: "ranking_only",
  event_cursor: 2,
  suggestions: {
    labels: 2,
    positive: 1,
    negative: 1,
    replay_samples: 2,
    drift_events: 0,
    promotion_threshold: 5,
  },
  transitions: {
    labels: 1,
    positive: 1,
    negative: 0,
    replay_samples: 1,
    drift_events: 0,
    promotion_threshold: 5,
  },
  prediction_errors: 0,
  corrections: 0,
  explicit_rules: 0,
  routine_patterns: [],
  workflow_patterns: 0,
  privacy: { raw_media_stored: false, secret_browsing: false, external_observation_requires_permission: true },
};

afterEach(cleanup);

describe("online learning reset", () => {
  beforeEach(() => {
    daemonMocks.call.mockReset();
  });

  it("requires a second click and surfaces daemon rejection", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "online_learning_status") return Promise.resolve(status);
      if (method === "online_learning_reset") {
        return Promise.resolve({ status: "error", message: "Reset checkpoint could not be written" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(OnlineLearningPanel);
    await fireEvent.click(await screen.findByRole("button", { name: "Reset learned adaptation" }));
    expect(screen.getByRole("button", { name: "Confirm reset learned adaptation" })).toBeTruthy();
    expect(daemonMocks.call).toHaveBeenCalledTimes(1);

    await fireEvent.click(screen.getByRole("button", { name: "Confirm reset learned adaptation" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Reset checkpoint could not be written");
    expect(daemonMocks.call).toHaveBeenCalledTimes(2);
  });
});
