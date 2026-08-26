import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import GatewayAuditLog from "./GatewayAuditLog.svelte";
import PermissionAuditLog from "./PermissionAuditLog.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));

vi.mock("../api/daemon", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/daemon")>();
  return { ...actual, call: daemonMocks.call };
});

afterEach(cleanup);

describe("security audit availability", () => {
  beforeEach(() => daemonMocks.call.mockReset());

  it("does not present an unavailable gateway audit as an empty log", async () => {
    daemonMocks.call.mockResolvedValue({
      status: "error",
      message: "Gateway audit store is not initialized.",
      events: [],
    });

    render(GatewayAuditLog);

    expect((await screen.findByRole("alert")).textContent).toContain("Gateway audit store is not initialized");
    expect(screen.queryByText("No gateway decisions recorded yet.")).toBeNull();
  });

  it("does not present an unavailable permission audit as an empty log", async () => {
    daemonMocks.call.mockResolvedValue({
      status: "error",
      message: "Permission audit store is not initialized.",
      events: [],
    });

    render(PermissionAuditLog);

    expect((await screen.findByRole("alert")).textContent).toContain("Permission audit store is not initialized");
    expect(screen.queryByText("No elevated permission decisions recorded yet.")).toBeNull();
  });
});
