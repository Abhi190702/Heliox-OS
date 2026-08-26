interface AirHandoffTarget {
  device_id: string;
}

export interface ReconciledAirHandoffTarget {
  selectedDeviceId: string;
  gestureArmed: boolean;
  targetChanged: boolean;
}

/**
 * Preserve an explicitly selected target while it exists. If it disappears,
 * choose a visible fallback for the UI but disarm the one-shot gesture so a
 * transfer can never be silently redirected to another device.
 */
export function reconcileAirHandoffTarget(
  selectedDeviceId: string,
  devices: AirHandoffTarget[],
  gestureArmed: boolean,
): ReconciledAirHandoffTarget {
  const selectedStillExists = devices.some((device) => device.device_id === selectedDeviceId);
  const nextSelectedDeviceId = selectedStillExists ? selectedDeviceId : devices[0]?.device_id || "";
  const targetChanged = Boolean(selectedDeviceId) && nextSelectedDeviceId !== selectedDeviceId;
  return {
    selectedDeviceId: nextSelectedDeviceId,
    gestureArmed: targetChanged ? false : gestureArmed,
    targetChanged,
  };
}
