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
});
