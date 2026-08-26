import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AgentMeshPanel from "./AgentMeshPanel.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});

afterEach(cleanup);

describe("specialist mesh result handling", () => {
  beforeEach(() => daemonMocks.call.mockReset());

  it("shows an unavailable mesh instead of rendering incomplete status", async () => {
    daemonMocks.call.mockResolvedValue({
      status: "error",
      enabled: false,
      message: "Agent mesh is not initialized",
    });

    render(AgentMeshPanel);

    expect((await screen.findByRole("alert")).textContent).toContain("Agent mesh is not initialized");
    expect(screen.queryByText("Total contracts")).toBeNull();
  });

  it("surfaces a missing specialist router during preview", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "agent_mesh_status") {
        return Promise.resolve({
          status: "ok",
          enabled: true,
          total_specialists: 0,
          executable_specialists: 0,
          external_capability_providers: 0,
          registered_action_types: 0,
          available_action_types: 0,
          coverage_complete: true,
          uncovered_action_types: [],
          sources: {},
          delegation: {
            maximum_depth: 3,
            maximum_fanout: 4,
            cycle_detection: true,
            full_transcript_handoffs: false,
            cancellation_propagation: true,
            partial_result_recovery: true,
            parallel_only_when_explicitly_independent: true,
          },
          routing: {
            fixed_numeric_ceiling: false,
            selection: "verified_outcomes",
            self_reported_success_authority: false,
          },
          specialists: [],
        });
      }
      if (method === "agent_routing") return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(AgentMeshPanel);
    await fireEvent.input(await screen.findByPlaceholderText(/inspect service logs/), {
      target: { value: "inspect the logs" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Specialist routing is unavailable");
  });
});
