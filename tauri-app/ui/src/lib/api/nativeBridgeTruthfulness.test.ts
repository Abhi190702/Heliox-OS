import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const rustRoot = resolve(process.cwd(), "../src-tauri/src");
const mainSource = readFileSync(resolve(rustRoot, "main.rs"), "utf-8");
const commandsSource = readFileSync(resolve(rustRoot, "commands.rs"), "utf-8");
const nativeBridgeSource = `${mainSource}\n${commandsSource}`;

describe("native bridge truthfulness", () => {
  it("does not infer agents, temperatures, security, or network rates", () => {
    expect(nativeBridgeSource).not.toContain("Healthy (0 threats / anomalies detected)");
    expect(nativeBridgeSource).not.toContain("Scanning system threats");
    expect(nativeBridgeSource).not.toContain("cpu_temp");
    expect(nativeBridgeSource).not.toContain('"network_up": "96 KB/s"');
    expect(nativeBridgeSource).not.toContain("background neural agents restarted and synchronized");
  });

  it("exposes explicit unavailable and limited-scope outcomes", () => {
    expect(mainSource).toContain("Hardware temperature sensors are unavailable");
    expect(mainSource).toContain("no native agent supervisor is configured");
    expect(commandsSource).toContain("no malware or threat scan was performed");
    expect(commandsSource).toContain("no agents were restarted");
  });
});
