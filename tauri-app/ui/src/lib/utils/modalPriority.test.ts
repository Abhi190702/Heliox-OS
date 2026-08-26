import { describe, expect, it } from "vitest";
import { selectActiveModal, type ModalSignals } from "./modalPriority";

const inactive: ModalSignals = {
  confirmation: false,
  rollback: false,
  interrupt: false,
  neural: false,
  budget: false,
  supervision: false,
};

describe("Heliox modal priority", () => {
  it("keeps an execution confirmation above every competing feature", () => {
    expect(
      selectActiveModal({
        confirmation: true,
        rollback: true,
        interrupt: true,
        neural: true,
        budget: true,
        supervision: true,
      }),
    ).toBe("confirmation");
  });

  it("queues advisory and budget modals behind a neural cancellation window", () => {
    expect(selectActiveModal({ ...inactive, neural: true, budget: true, supervision: true })).toBe("neural");
  });

  it("shows queued states in deterministic order as higher priorities clear", () => {
    expect(selectActiveModal({ ...inactive, interrupt: true, budget: true, supervision: true })).toBe("interrupt");
    expect(selectActiveModal({ ...inactive, budget: true, supervision: true })).toBe("budget");
    expect(selectActiveModal({ ...inactive, supervision: true })).toBe("supervision");
    expect(selectActiveModal(inactive)).toBeNull();
  });
});
