import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import GatewayPolicyEditor from "./GatewayPolicyEditor.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});

afterEach(cleanup);

describe("gateway policy result handling", () => {
  beforeEach(() => daemonMocks.call.mockReset());

  it("does not claim a rejected security policy was saved", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "gateway_policy_get") {
        return Promise.resolve({
          status: "ok",
          profiles: {
            autonomous: {
              max_tier: { shell: 1, browsing: 2, system_control: 1, other: 1 },
              deny_action_types: [],
              allow_root: false,
            },
          },
        });
      }
      if (method === "gateway_policy_update") {
        return Promise.resolve({ status: "error", message: "Policy validation failed" });
      }
      return Promise.resolve({ status: "ok" });
    });

    render(GatewayPolicyEditor);
    await fireEvent.click(await screen.findByRole("button", { name: "Save" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Policy validation failed");
    expect(daemonMocks.call.mock.calls).toEqual([
      ["gateway_policy_get"],
      ["gateway_policy_update", expect.any(Object)],
    ]);
    expect(screen.queryByText(/Saved/)).toBeNull();
  });
});
