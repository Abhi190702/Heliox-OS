/**
 * Shared helpers for visual regression tests.
 *
 * Because the app connects to a live Tauri/WebSocket daemon that won't be
 * running in CI, we mock the Tauri IPC bridge and the WebSocket session so
 * every panel renders in a deterministic, offline state.
 */

import type { Page } from "@playwright/test";

/**
 * Inject a minimal Tauri IPC stub so the app doesn't crash when it tries
 * to call `window.__TAURI_INTERNALS__` or `window.__TAURI__`.
 *
 * Must be called before page.goto().
 */
export async function mockTauriIpc(page: Page): Promise<void> {
  await page.addInitScript(() => {
    // Seed Math.random using mulberry32 to make all random layouts (like canvas nodes) completely deterministic
    const mulberry32 = (a: number) => {
      return () => {
        let t = a += 0x6D2B79F5;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    };
    Math.random = mulberry32(12345);

    // Mock Date.now to return a deterministic incrementing time to stabilize animations/timers
    let mockTime = 1716768000000;
    Date.now = () => {
      mockTime += 100;
      return mockTime;
    };

    // Minimal Tauri v2 internals stub
    (window as any).__TAURI_INTERNALS__ = {
      invoke: async (_cmd: string, _args?: unknown) => null,
      transformCallback: (cb: Function) => cb,
      convertFileSrc: (src: string) => src,
    };

    // Stub requestAnimationFrame and cancelAnimationFrame to freeze canvas animations
    (window as any).requestAnimationFrame = () => 999;
    (window as any).cancelAnimationFrame = () => {};

    // Stub the plugin APIs used by the app
    (window as any).__TAURI__ = {
      core: { invoke: async () => null },
      event: {
        listen: async () => () => {},
        once: async () => () => {},
        emit: async () => {},
      },
    };

    // Mock WebSocket to simulate daemon connection and intercept messages
    (window as any).WebSocket = class {
      static OPEN = 1;
      static CLOSED = 3;

      onopen: any;
      onmessage: any;
      onerror: any;
      onclose: any;
      readyState = 1; // WebSocket.OPEN
      
      constructor(url: string, protocols?: string | string[]) {
        (window as any).__mock_ws__ = this;
        
        // Auto-connect after a tiny delay
        setTimeout(() => {
          if (this.onopen) this.onopen(new Event("open"));
        }, 10);
      }
      
      send(data: string) {
        // Intercept sent messages and store them globally for tests to inspect
        const request = JSON.parse(data);
        (window as any).__last_ws_send__ = request;

        if (
          request.method === "risk_gate_status" &&
          (window as any).__mock_risk_gate_status_missing__
        ) {
          setTimeout(() => {
            this.onmessage?.({
              data: JSON.stringify({
                jsonrpc: "2.0",
                id: request.id,
                error: { code: -32601, message: "Method not found: risk_gate_status" },
              }),
            });
          }, 0);
          return;
        }

        if (request.method === "risk_gate_config_update") {
          (window as any).__risk_gate_enabled__ = request.params.enabled;
          (window as any).__risk_gate_update__ = request;
        }
        if (request.method === "self_healing_config_update") {
          (window as any).__self_healing_update__ = request;
        }
        if (request.method === "voice_gesture_workflow_submit") {
          (window as any).__workflow_submit__ = request;
        }
        if (request.method === "gesture_workflow_bindings_update") {
          (window as any).__gesture_workflow_update__ = request;
          (window as any).__gesture_workflow_policy__ = request.params;
        }
        if (
          request.method === "auth" ||
          request.method === "risk_gate_status" ||
          request.method === "risk_gate_config_update" ||
          request.method === "self_healing_status" ||
          request.method === "self_healing_config_update" ||
          request.method === "voice_gesture_workflow_list" ||
          request.method === "voice_gesture_workflow_submit" ||
          request.method === "gesture_workflow_bindings_get" ||
          request.method === "gesture_workflow_bindings_update"
        ) {
          let result: Record<string, unknown>;
          if (request.method === "auth") {
            result = { status: "ok" };
          } else if (request.method.startsWith("risk_gate_")) {
            result = {
                  status: "ok",
                  enabled: (window as any).__risk_gate_enabled__ ?? true,
                  weights_loaded: true,
                  model_version: "risk-mlp-v2-action-types",
                  training_samples: 36000,
                  embedding_size: 23,
                  learnable_action_types: [
                    "file_write",
                    "file_delete",
                    "service_start",
                    "service_stop",
                  ],
                  last_evaluation: {
                    evaluated_at: "2026-07-26T10:00:00Z",
                    action_count: 2,
                    risk_score: 0.8,
                    reasons: ["predicted disk usage 96% exceeds the safe threshold"],
                    worst_action_type: "file_write",
                    prediction_sources: ["learned", "rule"],
                  },
                };
          } else if (request.method.startsWith("self_healing_")) {
            result = {
              status: "ok",
              enabled: request.params?.enabled ?? true,
              auto_execute_max_tier: request.params?.auto_execute_max_tier ?? 1,
              watched_metrics: request.params?.watched_metrics ?? ["cpu", "memory", "disk"],
              monitors: {
                cpu: {
                  task_id: "monitor_cpu",
                  status: "running",
                  condition: "CPU > 80%",
                  interval_seconds: 10,
                  last_run: 1716768000,
                  run_count: 12,
                  error_count: 0,
                  last_result: { cpu_percent: 24 },
                },
                memory: {
                  task_id: "monitor_memory",
                  status: "running",
                  condition: "RAM > 85%",
                  interval_seconds: 15,
                  last_run: 1716768000,
                  run_count: 8,
                  error_count: 0,
                  last_result: { memory_percent: 58 },
                },
                disk: {
                  task_id: "monitor_disk",
                  status: "running",
                  condition: "Disk > 90%",
                  interval_seconds: 60,
                  last_run: 1716768000,
                  run_count: 2,
                  error_count: 0,
                  last_result: { disk_percent: 71 },
                },
              },
              attempts: [],
            };
          } else if (request.method === "voice_gesture_workflow_list") {
            result = { workflows: [] };
          } else if (request.method === "voice_gesture_workflow_submit") {
            result = {
              status: "submitted",
              workflow: {
                workflow_id: "wf_test",
                goal: request.params.goal,
                invocation_source: request.params.invocation_source,
                steps: [],
                current_step: 0,
                state: "pending",
                updated_at: "2026-07-26T10:00:00Z",
              },
            };
          } else if (request.method.startsWith("gesture_workflow_bindings_")) {
            const policy = (window as any).__gesture_workflow_policy__ ?? {
              enabled: false,
              bindings: [],
            };
            result = {
              status: "ok",
              enabled: policy.enabled,
              bindings: policy.bindings,
              supported_gestures: ["palm", "swipe_up", "thumbs_up"],
            };
          } else {
            result = {
              status: "ok",
              enabled: false,
              bindings: [],
            };
          }
          setTimeout(() => {
            this.onmessage?.({
              data: JSON.stringify({ jsonrpc: "2.0", id: request.id, result }),
            });
          }, 0);
        }
      }
      
      close() {
        this.readyState = 3; // WebSocket.CLOSED
        if (this.onclose) this.onclose(new Event("close"));
      }
    };
  });
}

/**
 * Helper to emit a daemon notification (e.g. status updates)
 */
export async function emitNotification(
  page: Page,
  method: string,
  params: Record<string, unknown>
): Promise<void> {
  await page.evaluate(
    ({ method, params }) => {
      const ws = (window as any).__mock_ws__;
      if (ws && ws.onmessage) {
        ws.onmessage({ data: JSON.stringify({ method, params }) });
      }
    },
    { method, params }
  );
  await page.waitForTimeout(80);
}

/**
 * Navigate to the app root and wait for the main window to be visible.
 * Skips the SetupWizard by pre-seeding localStorage.
 */
export async function gotoApp(
  page: Page,
  options: { riskGateStatusMissing?: boolean } = {}
): Promise<void> {
  if (options.riskGateStatusMissing) {
    await page.addInitScript(() => {
      (window as any).__mock_risk_gate_status_missing__ = true;
    });
  }
  await mockTauriIpc(page);

  // Pre-seed localStorage so the SetupWizard is skipped
  await page.addInitScript(() => {
    localStorage.setItem("heliox_first_run_complete", "true");
    // Minimal settings so the app doesn't crash on undefined reads
    localStorage.setItem(
      "heliox_settings",
      JSON.stringify({
        first_run_complete: true,
        theme: "dark",
        model: {
          provider: "ollama",
          ollama_model: "llama3.1:8b",
          mode: "lightweight",
          cloud_provider: "gemini",
          cloud_model: "",
          gpu_memory_limit_mb: 0,
        },
        security: {
          root_enabled: false,
          dry_run: false,
          snapshot_on_destructive: true,
          snapshot_retention_count: 10,
        },
        screen_vision: { capture_interval_seconds: 3 },
        restrictions: {
          protected_folders: [],
          protected_packages: [],
          blocked_commands: [],
        },
      })
    );
  });

  await page.goto("/");
  // Wait for the main window chrome to appear
  await page.waitForSelector(".window", { timeout: 15_000 });
}

/**
 * Click a top-level tab by its visible label.
 */
export async function clickTab(page: Page, label: string): Promise<void> {
  await page.click(`nav.tabs button:has-text("${label}")`);
  // Brief settle for Svelte transitions
  await page.waitForTimeout(300);
}

/**
 * Disable all CSS animations and transitions for pixel-stable screenshots.
 */
export async function freezeAnimations(page: Page): Promise<void> {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
      }
    `,
  });
}
