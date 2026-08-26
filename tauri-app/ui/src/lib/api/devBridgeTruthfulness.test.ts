import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const devBridgeSource = readFileSync(resolve(process.cwd(), "vite.config.ts"), "utf-8");

describe("browser development bridge truthfulness", () => {
  it("does not claim unverified health, agent, or sensor outcomes", () => {
    expect(devBridgeSource).not.toContain("Healthy (0 threats / anomalies detected)");
    expect(devBridgeSource).not.toContain("All 4 neural background agents");
    expect(devBridgeSource).not.toContain("Threat Containment Bridge initialized");
    expect(devBridgeSource).not.toContain("let count = 128");
    expect(devBridgeSource).not.toContain('network_up: "140 KB/s"');
    expect(devBridgeSource).not.toContain("cpu: 44");
  });

  it("marks unsupported commands as unavailable and measures disk usage locally", () => {
    expect(devBridgeSource).toContain("statfsSync(CONFIG_DIR)");
    expect(devBridgeSource).toContain("res.statusCode = status");
    expect(devBridgeSource).toContain("is unavailable in browser development");
  });

  it("runs only the fixed no-hardware neural benchmarks in browser development", () => {
    expect(devBridgeSource).toContain('command === "run_neural_benchmark"');
    expect(devBridgeSource).toContain('benchmark === "brainflow-synthetic"');
    expect(devBridgeSource).toContain('benchmark === "eegbci"');
    expect(devBridgeSource).toContain("const allowedRuns = new Set([4, 6, 8, 10, 12, 14])");
    expect(devBridgeSource).toContain('sendJson(res, 400, { error: "Unsupported neural benchmark" })');
    expect(devBridgeSource).toContain("execFile(");
    expect(devBridgeSource).not.toContain("exec(`${benchmark}");
  });

  it("reports the native neural sidecar as truthfully disconnected", () => {
    expect(devBridgeSource).toContain('command === "get_neural_sidecar_status"');
    expect(devBridgeSource).toContain("running: false");
    expect(devBridgeSource).toContain("available: false");
    expect(devBridgeSource).toContain("only available in the packaged Heliox desktop app");
  });
});
