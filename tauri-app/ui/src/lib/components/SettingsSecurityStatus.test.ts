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

  it("confirms destructive learning resets and validates wake-word status", () => {
    expect(source).toContain("RESET LEARNED GESTURE CALIBRATION?");
    expect(source).toContain("RESET LEARNED WAKE WORDS?");
    expect(source).toContain('(await call("list_wake_variants")) as DaemonStatusResult');
    expect(source).toContain('await call<DaemonStatusResult>("reset_wake_calibration")');
    expect(source).toContain("disabled={!voiceVariantsAvailable}");
  });

  it("requires acknowledged microphone enumeration before enabling selection", () => {
    expect(source).toContain('>("list_audio_input_devices")');
    expect(source).toContain('requireOkResult(result, "Microphone inputs are unavailable.")');
    expect(source).toContain("disabled={speechSaving || audioInputDevices.length === 0}");
  });
});
