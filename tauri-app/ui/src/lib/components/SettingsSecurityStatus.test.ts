import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Settings security status wiring", () => {
  const source = readFileSync(resolve("src/lib/components/SettingsPanel.svelte"), "utf8");

  it("requires acknowledged root and snapshot status before enabling mutations", () => {
    expect(source).toContain('(await call("get_security_status")) as DaemonStatusResult');
    expect(source).toContain('(await call("get_snapshot_status")) as DaemonStatusResult');
    expect(source).toContain("disabled={rootSaving || !rootRuntime}");
    expect(source).toContain("disabled={snapshotSaving || !snapshotRuntime}");
  });
});
