import { describe, expect, it } from "vitest";
import { vi } from "vitest";
import {
  dispatchGestureToOwner,
  latchedGestureAfterCursorOverride,
  ownerOverridesCursorMode,
  selectGestureDispatchOwner,
  type GestureDispatchOwner,
} from "./gestureDispatchPolicy";

describe("selectGestureDispatchOwner", () => {
  it("keeps paused-workflow controls above every other consumer", () => {
    expect(
      selectGestureDispatchOwner({
        hasPendingWorkflow: true,
        controlIntent: "cancel",
        handoffCommand: "drop",
        hasBoundWorkflow: true,
      }),
    ).toBe("workflow_control");
  });

  it("lets an explicitly armed handoff claim its current command", () => {
    expect(
      selectGestureDispatchOwner({
        hasPendingWorkflow: false,
        controlIntent: "unknown",
        handoffCommand: "grab",
        hasBoundWorkflow: true,
      }),
    ).toBe("air_handoff");
  });

  it("allows a handoff command unrelated to a pending workflow control", () => {
    expect(
      selectGestureDispatchOwner({
        hasPendingWorkflow: true,
        controlIntent: "unknown",
        handoffCommand: "grab",
        hasBoundWorkflow: true,
      }),
    ).toBe("air_handoff");
  });

  it("uses a binding only when no workflow is already waiting", () => {
    expect(
      selectGestureDispatchOwner({
        hasPendingWorkflow: false,
        controlIntent: "unknown",
        handoffCommand: "none",
        hasBoundWorkflow: true,
      }),
    ).toBe("bound_workflow");
    expect(
      selectGestureDispatchOwner({
        hasPendingWorkflow: true,
        controlIntent: "unknown",
        handoffCommand: "none",
        hasBoundWorkflow: true,
      }),
    ).toBe("default");
  });

  it("sends only an unclaimed gesture to the default path", () => {
    expect(
      selectGestureDispatchOwner({
        hasPendingWorkflow: false,
        controlIntent: "unknown",
        handoffCommand: "none",
        hasBoundWorkflow: false,
      }),
    ).toBe("default");
  });

  it.each<GestureDispatchOwner>(["workflow_control", "air_handoff", "bound_workflow", "default"])(
    "dispatches the %s owner exactly once without leaking to another feature",
    async (owner) => {
      const handlers = {
        workflow_control: vi.fn(),
        air_handoff: vi.fn(),
        bound_workflow: vi.fn(),
        default: vi.fn(),
      };

      await dispatchGestureToOwner(owner, handlers);

      for (const [name, handler] of Object.entries(handlers)) {
        expect(handler).toHaveBeenCalledTimes(name === owner ? 1 : 0);
      }
    },
  );

  it("lets safety workflow and armed handoff commands override cursor mode", () => {
    expect(ownerOverridesCursorMode("workflow_control")).toBe(true);
    expect(ownerOverridesCursorMode("air_handoff")).toBe(true);
    expect(ownerOverridesCursorMode("bound_workflow")).toBe(false);
    expect(ownerOverridesCursorMode("default")).toBe(false);
  });

  it("releases the recognized-gesture latch for cursor overrides", () => {
    expect(latchedGestureAfterCursorOverride("workflow_control", "thumbs_up")).toBe("");
    expect(latchedGestureAfterCursorOverride("air_handoff", "pinch")).toBe("");
    expect(latchedGestureAfterCursorOverride("bound_workflow", "peace")).toBe("peace");
    expect(latchedGestureAfterCursorOverride("default", "palm")).toBe("palm");
  });
});
