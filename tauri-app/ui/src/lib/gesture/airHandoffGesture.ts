export type AirHandoffGestureCommand = "grab" | "drop" | "cancel" | "none";

export function airHandoffGestureCommand(
  armed: boolean,
  holdingDraft: boolean,
  gesture: string,
): AirHandoffGestureCommand {
  if (!armed) return "none";
  if (!holdingDraft && gesture === "fist") return "grab";
  if (holdingDraft && (gesture === "palm" || gesture === "palm_push")) return "drop";
  if (holdingDraft && gesture === "palm_pull") return "cancel";
  return "none";
}
