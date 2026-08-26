import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const componentRoot = resolve(process.cwd(), "src/lib/components");
const quickActionSource = readFileSync(resolve(componentRoot, "QuickAction.svelte"), "utf-8");
const voiceControlSource = readFileSync(resolve(componentRoot, "VoiceControl.svelte"), "utf-8");

describe("voice command coordinator wiring", () => {
  it("routes the dashboard action through the single shared voice controller", () => {
    expect(quickActionSource).toContain('new CustomEvent("heliox:voice-command-request"');
    expect(quickActionSource).not.toContain("new SpeechRec");
    expect(voiceControlSource).toContain(
      'window.addEventListener("heliox:voice-command-request", handleVoiceCommandRequest)',
    );
    expect(voiceControlSource).toContain("await session.sendCommand(text)");
  });
});
