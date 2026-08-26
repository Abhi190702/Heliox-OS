import type { AirHandoffGestureCommand } from "./airHandoffGesture";
import type { GestureControlIntent } from "./workflowControl";

export type GestureDispatchOwner = "workflow_control" | "air_handoff" | "bound_workflow" | "default";

export type GestureDispatchHandlers = Record<GestureDispatchOwner, () => void | Promise<void>>;

interface GestureDispatchContext {
  hasPendingWorkflow: boolean;
  controlIntent: GestureControlIntent;
  handoffCommand: AirHandoffGestureCommand;
  hasBoundWorkflow: boolean;
}

/** Select exactly one owner for a recognized gesture. */
export function selectGestureDispatchOwner(context: GestureDispatchContext): GestureDispatchOwner {
  if (context.hasPendingWorkflow && context.controlIntent !== "unknown") return "workflow_control";
  if (context.handoffCommand !== "none") return "air_handoff";
  if (!context.hasPendingWorkflow && context.hasBoundWorkflow) return "bound_workflow";
  return "default";
}

/** Runs only the handler selected by the arbitration policy. */
export async function dispatchGestureToOwner(
  owner: GestureDispatchOwner,
  handlers: GestureDispatchHandlers,
): Promise<void> {
  await handlers[owner]();
}

/** Safety/workflow owners may exit cursor mode; ordinary bindings and defaults stay suppressed. */
export function ownerOverridesCursorMode(owner: GestureDispatchOwner): boolean {
  return owner === "workflow_control" || owner === "air_handoff";
}

/** Release the display/debounce latch when a higher-priority owner exits cursor mode. */
export function latchedGestureAfterCursorOverride(owner: GestureDispatchOwner, currentGesture: string): string {
  return ownerOverridesCursorMode(owner) ? "" : currentGesture;
}
