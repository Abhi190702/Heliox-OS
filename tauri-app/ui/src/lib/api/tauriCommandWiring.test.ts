import { readdirSync, readFileSync, statSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return [".ts", ".svelte"].includes(extname(path)) ? [path] : [];
  });
}

function literalInvocations(source: string, functionName: string): string[] {
  const pattern = new RegExp(`\\b${functionName}(?:<[^>]*>)?\\(\\s*["']([a-zA-Z0-9_]+)["']`, "g");
  return [...source.matchAll(pattern)].map((match) => match[1]);
}

describe("Tauri command wiring", () => {
  it("registers every literal native command invoked by the UI", () => {
    const uiRoot = resolve(process.cwd(), "src");
    const invoked = new Set<string>();

    for (const path of sourceFiles(uiRoot)) {
      if (path.includes(".test.")) continue;
      if (path.endsWith(`${join("api", "invoke.ts")}`)) continue;
      const source = readFileSync(path, "utf-8");
      const importsInvokeWrapper =
        /from\s+["'][^"']*api\/invoke["']/.test(source) || /from\s+["']\.\/invoke["']/.test(source);
      const importsTauriInvoke = /import\s*\{[^}]*\binvoke\b[^}]*\}\s*from\s*["']@tauri-apps\/api\/core["']/.test(
        source,
      );
      if (importsInvokeWrapper || importsTauriInvoke) {
        literalInvocations(source, "invoke").forEach((command) => invoked.add(command));
      }
      literalInvocations(source, "tauriInvoke").forEach((command) => invoked.add(command));
    }

    const nativeSource = readFileSync(resolve(process.cwd(), "../src-tauri/src/main.rs"), "utf-8");
    const handler = nativeSource.match(/generate_handler!\[([\s\S]*?)\]\)/)?.[1] ?? "";
    const registered = new Set(
      handler
        .split(",")
        .map((entry) => entry.trim().split("::").pop() ?? "")
        .filter(Boolean),
    );
    const missing = [...invoked].filter((command) => !registered.has(command)).sort();

    expect(missing, `Unregistered UI commands: ${missing.join(", ")}`).toEqual([]);
  });
});
