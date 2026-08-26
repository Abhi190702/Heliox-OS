import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../i18n";
import EvolutionHarnessPanel from "./EvolutionHarnessPanel.svelte";
import StrategyEvolutionPanel from "./StrategyEvolutionPanel.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});

afterEach(cleanup);

describe("evolution panel result handling", () => {
  beforeEach(() => {
    daemonMocks.call.mockReset();
  });

  it("does not claim an evolution run exists after daemon rejection", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "evolution_status") {
        return Promise.resolve({
          enabled: true,
          runner: { available: true, backend: "docker", image: "runner", image_id: "image-1" },
          profiles: {},
          run_counts: {},
          candidate_counts: {},
          restrictions: {},
        });
      }
      if (method === "evolution_runs") return Promise.resolve({ runs: [] });
      if (method === "evolution_candidates") return Promise.resolve({ candidates: [] });
      if (method === "evolution_create_run") {
        return Promise.resolve({ status: "error", message: "Isolation archive is read-only" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(EvolutionHarnessPanel);
    await fireEvent.input(await screen.findByLabelText("Bounded failure or opportunity"), {
      target: { value: "Repair a reproducible planner failure" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Create inert run" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Isolation archive is read-only");
    expect(screen.queryByText(/Run created at the current Git commit/)).toBeNull();
  });

  it("does not claim a strategy candidate was stored after daemon rejection", async () => {
    daemonMocks.call.mockImplementation((method: string) => {
      if (method === "strategy_evolution_status") {
        return Promise.resolve({
          enabled: true,
          algorithm: "gepa",
          candidate_counts: {},
          pareto_front: [],
          assignments: {},
          promotion: {
            automatic: false,
            shadow_samples_required: 10,
            canary_samples_required: 10,
            exact_id_confirmation_required: true,
          },
        });
      }
      if (method === "strategy_candidates") return Promise.resolve({ candidates: [] });
      if (method === "strategy_propose") {
        return Promise.resolve({ status: "error", message: "Strategy archive is unavailable" });
      }
      throw new Error(`unexpected method: ${method}`);
    });

    render(StrategyEvolutionPanel);
    await fireEvent.click(screen.getByRole("button", { name: "Propose candidate" }));
    await fireEvent.input(screen.getByLabelText("Complete candidate text"), {
      target: { value: "Use evidence before selecting a tool." },
    });
    await fireEvent.input(screen.getByLabelText("Trace-grounded rationale"), {
      target: { value: "A trace selected an unavailable tool." },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Store candidate" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Strategy archive is unavailable");
    expect(screen.queryByText(/Candidate stored in isolation/)).toBeNull();
  });
});
