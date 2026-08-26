import { describe, expect, it } from "vitest";
import { reconcileAirHandoffTarget } from "./airHandoffTarget";

describe("reconcileAirHandoffTarget", () => {
  it("keeps an armed gesture bound to the selected device", () => {
    expect(reconcileAirHandoffTarget("phone-a", [{ device_id: "phone-a" }, { device_id: "phone-b" }], true)).toEqual({
      selectedDeviceId: "phone-a",
      gestureArmed: true,
      targetChanged: false,
    });
  });

  it("disarms instead of silently redirecting to another paired device", () => {
    expect(reconcileAirHandoffTarget("phone-a", [{ device_id: "phone-b" }], true)).toEqual({
      selectedDeviceId: "phone-b",
      gestureArmed: false,
      targetChanged: true,
    });
  });

  it("disarms when the selected device list becomes empty", () => {
    expect(reconcileAirHandoffTarget("phone-a", [], true)).toEqual({
      selectedDeviceId: "",
      gestureArmed: false,
      targetChanged: true,
    });
  });

  it("may choose the first device when there was no prior explicit target", () => {
    expect(reconcileAirHandoffTarget("", [{ device_id: "phone-a" }], false)).toEqual({
      selectedDeviceId: "phone-a",
      gestureArmed: false,
      targetChanged: false,
    });
  });
});
