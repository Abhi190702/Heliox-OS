export interface AirHandoffDeliveryEvent {
  event: string;
  transfer_id?: string;
  device_id?: string;
  at: number;
}

export interface AirHandoffDeliveryResolution {
  awaitingTransferId: string;
  message: string;
}

export function resolveAirHandoffDelivery(
  awaitingTransferId: string,
  events: AirHandoffDeliveryEvent[],
  targetName: string,
): AirHandoffDeliveryResolution | null {
  if (!awaitingTransferId) return null;
  const outcome = events.find(
    (event) =>
      event.transfer_id === awaitingTransferId && (event.event === "acknowledged" || event.event === "expired"),
  );
  if (!outcome) return null;
  return {
    awaitingTransferId: "",
    message:
      outcome.event === "acknowledged"
        ? `${targetName} confirmed receipt`
        : `${targetName} did not confirm receipt before the handoff expired`,
  };
}
