import { describe, expect, it } from "vitest";

import { resolveAirHandoffDelivery } from "./airHandoffDelivery";

describe("resolveAirHandoffDelivery", () => {
  it("reports an explicit receiver acknowledgement", () => {
    expect(
      resolveAirHandoffDelivery("transfer-1", [{ event: "acknowledged", transfer_id: "transfer-1", at: 10 }], "Phone"),
    ).toEqual({ awaitingTransferId: "", message: "Phone confirmed receipt" });
  });

  it("reports expiry without claiming delivery", () => {
    expect(
      resolveAirHandoffDelivery("transfer-1", [{ event: "expired", transfer_id: "transfer-1", at: 10 }], "Phone"),
    ).toEqual({
      awaitingTransferId: "",
      message: "Phone did not confirm receipt before the handoff expired",
    });
  });

  it("ignores unrelated and still-pending events", () => {
    expect(
      resolveAirHandoffDelivery(
        "transfer-1",
        [
          { event: "acknowledged", transfer_id: "transfer-2", at: 10 },
          { event: "dropped", transfer_id: "transfer-1", at: 9 },
        ],
        "Phone",
      ),
    ).toBeNull();
  });
});
