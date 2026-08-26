import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import GitConflictResolver from "./GitConflictResolver.svelte";

const mocks = vi.hoisted(() => ({
  call: vi.fn(),
  invoke: vi.fn(),
  isTauriRuntime: vi.fn(() => false),
}));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: mocks.call };
});
vi.mock("../api/invoke", () => ({ invoke: mocks.invoke }));
vi.mock("../utils/runtime", () => ({ isTauriRuntime: mocks.isTauriRuntime }));
vi.mock("../stores/session", () => ({ session: { addSystemMessage: vi.fn() } }));

afterEach(cleanup);

describe("Git conflict resolution results", () => {
  beforeEach(() => {
    mocks.call.mockReset();
    mocks.invoke.mockReset();
    mocks.isTauriRuntime.mockReset();
    mocks.isTauriRuntime.mockReturnValue(false);
  });

  it("does not report success when the browser RPC rejects a resolution", async () => {
    mocks.call.mockResolvedValue({ status: "error", message: "The conflict block changed on disk" });

    render(GitConflictResolver, {
      payload: {
        status: "conflicts_found",
        conflicts: [
          {
            path: "src/example.ts",
            original_hunk: "const value = 1;",
            conflict_hunk: "const value = 2;",
            proposed_resolution_code: "const value = 3;",
            full_block: "<<<<<<< HEAD\nconst value = 1;\n=======\nconst value = 2;\n>>>>>>> branch",
          },
        ],
      },
    });

    await fireEvent.click(screen.getByRole("button", { name: "Apply Resolution" }));

    expect((await screen.findByRole("alert")).textContent).toContain("The conflict block changed on disk");
    expect(screen.queryByText("Successfully resolved and saved to disk.")).toBeNull();
  });

  it("validates application-level results from the native bridge too", async () => {
    mocks.isTauriRuntime.mockReturnValue(true);
    mocks.invoke.mockResolvedValue({ status: "error", message: "Resolution was not written" });

    render(GitConflictResolver, {
      payload: {
        status: "conflicts_found",
        conflicts: [
          {
            path: "src/example.ts",
            original_hunk: "old",
            conflict_hunk: "new",
            proposed_resolution_code: "merged",
            full_block: "conflict",
          },
        ],
      },
    });

    await fireEvent.click(screen.getByRole("button", { name: "Apply Resolution" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Resolution was not written");
    expect(screen.queryByText("Successfully resolved and saved to disk.")).toBeNull();
  });
});
