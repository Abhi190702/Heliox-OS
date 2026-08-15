import { describe, expect, it } from "vitest";
import { airHandoffGestureCommand } from "./airHandoffGesture";

describe("airHandoffGestureCommand", () => {
  it("never claims gestures until the user explicitly arms a handoff", () => {
    expect(airHandoffGestureCommand(false, false, "fist")).toBe("none");
    expect(airHandoffGestureCommand(false, true, "palm_push")).toBe("none");
  });

  it("uses a fist to grab and an open-palm push to drop", () => {
    expect(airHandoffGestureCommand(true, false, "fist")).toBe("grab");
    expect(airHandoffGestureCommand(true, true, "palm_push")).toBe("drop");
    expect(airHandoffGestureCommand(true, true, "palm")).toBe("drop");
  });

  it("uses palm pull as a fail-safe cancellation while holding content", () => {
    expect(airHandoffGestureCommand(true, true, "palm_pull")).toBe("cancel");
    expect(airHandoffGestureCommand(true, false, "palm_pull")).toBe("none");
  });
});
