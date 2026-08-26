import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pollAfterSuccessfulProbe } from "./polling";

describe("pollAfterSuccessfulProbe", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("does not poll after an unavailable capability probe", async () => {
    const probe = vi.fn().mockResolvedValue(false);
    pollAfterSuccessfulProbe(probe, 1_000);
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(probe).toHaveBeenCalledTimes(1);
  });

  it("polls a supported capability until cleanup", async () => {
    const probe = vi.fn().mockResolvedValue(true);
    const cleanup = pollAfterSuccessfulProbe(probe, 1_000);
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(2_000);
    expect(probe).toHaveBeenCalledTimes(3);

    cleanup();
    await vi.advanceTimersByTimeAsync(2_000);
    expect(probe).toHaveBeenCalledTimes(3);
  });
});
